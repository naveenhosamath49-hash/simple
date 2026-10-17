from __future__ import annotations

import abc
import datetime
import hashlib
import logging
import re
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def normalize_url(raw_url: str) -> str:
    """
    Produce canonical URL by:
    - Stripping trailing slashes
    - Removing tracking/marketing query parameters (utm_*, ref, fbclid, etc.)
    - Converting scheme and domain to lowercase
    - Removing URL fragments (#section)
    """
    if not raw_url:
        return ""
    try:
        parsed = urlparse(raw_url.strip())
        # Filter query params
        query_params = parse_qsl(parsed.query, keep_blank_values=False)
        tracking_prefixes = ("utm_", "fbclid", "gclid", "ref", "source", "affiliate", "mc_cid", "mc_eid")
        filtered_params = [
            (k, v) for k, v in query_params if not any(k.lower().startswith(prefix) for prefix in tracking_prefixes)
        ]
        # Sort parameters deterministically
        filtered_params.sort(key=lambda x: x[0])
        new_query = urlencode(filtered_params)

        clean_path = parsed.path.rstrip("/")
        if not clean_path:
            clean_path = ""

        canonical = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            "",
            new_query,
            "",
        ))
        return canonical
    except Exception:
        return raw_url.strip()


def compute_article_hash(canonical_url: str, title: str) -> str:
    """Generate SHA-256 deterministic hash from canonical URL and normalized title."""
    clean_title = re.sub(r"\s+", " ", title.strip().lower())
    payload = f"{canonical_url}|{clean_title}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class NormalizedArticle(BaseModel):
    """Common normalized data contract across all news sources."""
    original_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    content: Optional[str] = None
    url: str = Field(..., min_length=5, max_length=2048)
    canonical_url: str = Field(..., min_length=5, max_length=2048)
    article_hash: str = Field(..., min_length=64, max_length=64)
    image_url: Optional[str] = None
    publisher_name: str = Field(..., min_length=1, max_length=255)
    publisher_domain: Optional[str] = None
    author: Optional[str] = None
    published_at: datetime.datetime
    language: str = "en"
    country: str = "us"
    category: str = "General"
    source_type: str = "unknown"
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert normalized article to DB dictionary representation."""
        return {
            "original_id": self.original_id,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "article_hash": self.article_hash,
            "image_url": self.image_url,
            "publisher_name": self.publisher_name,
            "publisher_domain": self.publisher_domain,
            "author": self.author,
            "published_at": self.published_at,
            "language": self.language,
            "country": self.country,
            "category": self.category,
            "source_type": self.source_type,
            "raw_metadata": self.raw_metadata,
        }


class BaseConnector(abc.ABC):
    """Abstract base connector interface for all news ingestion sources."""

    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    def fetch_articles(self, **kwargs) -> List[NormalizedArticle]:
        """Fetch raw articles from provider, validate, and return normalized list."""
        pass

    @abc.abstractmethod
    def validate_response(self, response_data: Any) -> bool:
        """Validate structural integrity of incoming API response payload."""
        pass

    @abc.abstractmethod
    def normalize_article(self, raw_item: Dict[str, Any]) -> Optional[NormalizedArticle]:
        """Map provider-specific payload to standard NormalizedArticle."""
        pass

    def report_errors(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Structured error logging and telemetry."""
        ctx_str = f" Context: {context}" if context else ""
        logger.error(f"[{self.name}] Error during connector execution: {str(error)}.{ctx_str}", exc_info=True)
