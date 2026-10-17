from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse
from typing import Optional


# Private and reserved IP networks for SSRF mitigation
DISALLOWED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # RFC 1918 Private
    ipaddress.ip_network("172.16.0.0/12"),    # RFC 1918 Private
    ipaddress.ip_network("192.168.0.0/16"),   # RFC 1918 Private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-Local (Cloud metadata)
    ipaddress.ip_network("0.0.0.0/8"),        # Broadcast/Current network
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]

DISALLOWED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
}

# Regex to detect common prompt injection signatures
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+(developer|unrestricted|god)\s+mode", re.IGNORECASE),
    re.compile(r"system\s*override", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    re.compile(r"```(system|instruction)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(dan|jailbreak)", re.IGNORECASE),
]


def validate_url(url: str, allow_private: bool = False) -> bool:
    """
    Validate that an external URL is well-formed and does not point to internal/SSRF targets.
    
    Returns True if valid and safe, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Only permit HTTP and HTTPS schemes
    if parsed.scheme.lower() not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    hostname_clean = hostname.lower()
    if hostname_clean in DISALLOWED_HOSTS:
        return False

    # Block common cloud metadata services
    if "metadata" in hostname_clean or "internal" in hostname_clean:
        return False

    if allow_private:
        return True

    # Check if host is a literal IP address
    try:
        ip = ipaddress.ip_address(hostname_clean)
        for network in DISALLOWED_NETWORKS:
            if ip in network:
                return False
        return True
    except ValueError:
        pass  # Hostname is a domain name, not an IP literal

    # Resolve domain to IP to catch DNS rebinding and internal resolutions
    try:
        addr_info = socket.getaddrinfo(hostname_clean, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            for network in DISALLOWED_NETWORKS:
                if ip in network:
                    return False
    except (socket.gaierror, socket.herror, ValueError):
        # Could not resolve host at this time; if it looks like a valid FQDN, permit with caution
        # but require valid TLD format
        if not re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", hostname_clean):
            return False

    return True


def is_safe_redirect(target_url: str) -> bool:
    """Verify redirection targets to prevent open redirect vulnerabilities."""
    return validate_url(target_url, allow_private=False)


def sanitize_text(text: Optional[str], max_length: int = 10000) -> str:
    """
    Clean raw input text:
    - Strip null bytes and non-printable control characters (except newline, tab).
    - Normalize whitespace.
    - Truncate to maximum permitted length to prevent memory/token exhaustion.
    """
    if not text:
        return ""

    # Remove null bytes and non-printable chars
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or (ch >= " " and ord(ch) != 127))

    # Normalize repeated newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Trim to bounds
    return text[:max_length].strip()


def sanitize_for_prompt(text: Optional[str], max_length: int = 5000) -> str:
    """
    Sanitize untrusted news text before including in LLM prompt.
    - Flags or defangs direct prompt injection attempts.
    - Replaces delimiter tags that could break XML encapsulation.
    - Encapsulates text so the LLM strictly treats it as reference data.
    """
    cleaned = sanitize_text(text, max_length=max_length)
    if not cleaned:
        return "[Empty article content]"

    # Neutralize dangerous boundary tags
    cleaned = cleaned.replace("</untrusted_article>", "[tag_neutralized]")
    cleaned = cleaned.replace("<untrusted_article>", "[tag_neutralized]")
    cleaned = cleaned.replace("```json", "[code_fence]")
    cleaned = cleaned.replace("```", "[fence]")

    # Check for prompt injection attempts and neutralize their imperative impact
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(cleaned):
            cleaned = pattern.sub(r"[POTENTIAL_INJECTION_DEFANGED: \g<0>]", cleaned)

    return f"<untrusted_article>\n{cleaned}\n</untrusted_article>"


def mask_secret(secret: Optional[str], visible_chars: int = 4) -> str:
    """Mask a sensitive API key or token for safe logging/display."""
    if not secret:
        return "[NOT_SET]"
    if len(secret) <= visible_chars * 2:
        return "***"
    return f"{secret[:visible_chars]}...{secret[-visible_chars:]}"
