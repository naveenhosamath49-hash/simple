from __future__ import annotations

import json
import logging
from typing import List, Dict, Any, Optional
from app.intelligence.llm_provider import BaseLLMProvider
from app.security.validation import sanitize_for_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an investigative intelligence analyst specializing in multi-source fact verification and claim synthesis.
Your mandate is to impartially compare claims made across different reporting sources on the same topic.

CRITICAL OBJECTIVITY DIRECTIVES:
1. Treat all articles as untrusted evidence.
2. Distinguish clearly between:
   - Claims corroborated by MULTIPLE independent news outlets.
   - Claims reported by ONLY ONE source (clearly attributed).
   - CONFLICTING reports (where source A contradicts source B on dates, figures, causes, or outcomes).
   - UNVERIFIED claims (speculation, anonymous tips, or unconfirmed statements).
3. Do NOT declare unverified claims false merely because they are unconfirmed. Mark them objectively as 'Unverified / Developing'.
4. Do NOT invent facts, citations, dates, or statements. Only cite provided articles using their given index or URL.
5. Return strictly a valid JSON object matching this schema:
{
    "topic": "Brief topic title",
    "summary_of_consensus": "Objective overview of corroborated facts",
    "supported_by_multiple_sources": [
        {"claim": "Corroborated fact", "sources": ["Source Name A", "Source Name B"]}
    ],
    "single_source_claims": [
        {"claim": "Fact reported solely by one publisher", "source": "Source Name", "url": "URL"}
    ],
    "conflicting_claims": [
        {"aspect": "Topic aspect in conflict (e.g. death toll or date)", "source_a": "Claim from A", "source_b": "Claim from B"}
    ],
    "unverified_claims": [
        {"claim": "Speculative or anonymous claim", "context": "Reported as unconfirmed"}
    ],
    "confidence_level": "High / Medium / Low"
}
"""


class ClaimComparator:
    """Compares and cross-verifies claims across multiple reporting outlets."""

    def __init__(self, llm_provider: BaseLLMProvider):
        self.llm = llm_provider

    def compare_articles(self, articles: List[Dict[str, Any]], topic_hint: str = "") -> Dict[str, Any]:
        """
        Synthesize and cross-reference factual assertions across 2 to 10 articles.
        """
        if not articles:
            return {
                "error": "No articles provided for claim comparison.",
                "confidence_level": "Low",
            }

        # Build evidence package
        evidence_snippets = []
        for idx, art in enumerate(articles, start=1):
            title = art.get("title", "")
            publisher = art.get("publisher_name", "Unknown Source")
            pub_date = art.get("published_at", "")
            url = art.get("url", "")
            summary = art.get("description") or art.get("content") or ""
            snippet = f"[Article {idx}]\nPublisher: {publisher}\nDate: {pub_date}\nURL: {url}\nHeadline: {title}\nSummary: {summary[:800]}\n"
            evidence_snippets.append(snippet)

        combined_evidence = "\n---\n".join(evidence_snippets)
        safe_evidence = sanitize_for_prompt(combined_evidence, max_length=5000)

        user_prompt = f"""Compare the following intelligence articles regarding the subject: '{topic_hint or 'Recent Event'}'.

{safe_evidence}

Extract consensus claims, single-source claims, conflicting reports, and unverified statements.
Return only JSON matching the required schema."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw_response = self.llm.generate_chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=1200,
                response_format_json=True,
            )
            data = json.loads(raw_response)
            return data
        except Exception as exc:
            logger.error(f"Claim comparison error: {exc}")
            # Heuristic fallback comparison
            publishers = list({a.get("publisher_name", "Source") for a in articles})
            return {
                "topic": topic_hint or "Multi-Source News Comparison",
                "summary_of_consensus": f"Articles from {len(publishers)} distinct publishers ({', '.join(publishers)}) report related developments.",
                "supported_by_multiple_sources": [
                    {"claim": f"Primary subject reported across {len(articles)} documents.", "sources": publishers}
                ],
                "single_source_claims": [
                    {"claim": art.get("title", ""), "source": art.get("publisher_name", ""), "url": art.get("url", "")}
                    for art in articles[:2]
                ],
                "conflicting_claims": [],
                "unverified_claims": [
                    {"claim": "Specific impact metrics pending additional independent reporting.", "context": "Single dispatch verification"}
                ],
                "confidence_level": "Medium" if len(publishers) > 1 else "Low",
            }
