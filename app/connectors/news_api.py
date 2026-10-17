from __future__ import annotations

import datetime
import logging
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
import httpx
from dateutil import parser as date_parser

from app.config import settings
from app.connectors.base import BaseConnector, NormalizedArticle, normalize_url, compute_article_hash
from app.security.validation import validate_url, sanitize_text

logger = logging.getLogger(__name__)


class NewsAPIConnector(BaseConnector):
    """
    Official News API (https://newsapi.org/docs) connector.
    Supports /v2/top-headlines, /v2/everything, and /v2/top-headlines/sources.
    Implements retry logic with exponential backoff, rate limit tracking, and safe fallbacks.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        super().__init__(name="NewsAPI")
        self.api_key = api_key or settings.NEWS_API_KEY
        self.base_url = (base_url or settings.NEWS_API_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def is_configured(self) -> bool:
        """Check whether a non-empty API key is configured."""
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your_news_api_key_here")

    def _get_headers(self) -> Dict[str, str]:
        """Generate authentication headers."""
        return {
            "X-Api-Key": self.api_key or "",
            "User-Agent": "AINewsIntelligenceAgent/1.0",
            "Accept": "application/json",
        }

    def _execute_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute HTTP GET request with exponential backoff and rate-limit inspection.
        """
        if not self.is_configured():
            logger.warning("[NewsAPI] Missing or placeholder API key. Operating in graceful fallback mode.")
            return {"status": "error", "code": "apiKeyMissing", "message": "NEWS_API_KEY is not configured in .env."}

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        cleaned_params = {k: v for k, v in params.items() if v is not None}

        delay = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=cleaned_params, headers=self._get_headers())

                # Check rate limit headers if present
                rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
                if rate_limit_remaining is not None:
                    logger.debug(f"[NewsAPI] Rate limit remaining: {rate_limit_remaining}")

                # Rate limited
                if response.status_code == 429:
                    logger.warning(f"[NewsAPI] Rate limit reached (HTTP 429). Attempt {attempt}/{self.max_retries}.")
                    if attempt == self.max_retries:
                        return {
                            "status": "error",
                            "code": "rateLimited",
                            "message": "NewsAPI rate limit exhausted (HTTP 429).",
                        }
                    time.sleep(delay)
                    delay *= 2
                    continue

                # Authentication error
                if response.status_code == 401:
                    logger.error("[NewsAPI] Invalid API key (HTTP 401).")
                    return {
                        "status": "error",
                        "code": "apiKeyInvalid",
                        "message": "Invalid or disabled NewsAPI key.",
                    }

                # Bad Request
                if response.status_code == 400:
                    data = response.json()
                    logger.error(f"[NewsAPI] Bad request: {data.get('message')}")
                    return data

                # Server error (5xx)
                if response.status_code >= 500:
                    logger.warning(f"[NewsAPI] Server error (HTTP {response.status_code}). Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                    continue

                response.raise_for_status()
                return response.json()

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                self.report_errors(exc, {"endpoint": endpoint, "attempt": attempt})
                if attempt == self.max_retries:
                    return {
                        "status": "error",
                        "code": "networkError",
                        "message": f"Connection failed after {self.max_retries} attempts: {str(exc)}",
                    }
                time.sleep(delay)
                delay *= 2

        return {"status": "error", "code": "unknownError", "message": "Failed to retrieve data from NewsAPI."}

    def validate_response(self, response_data: Any) -> bool:
        """Verify that response matches the official News API payload contract."""
        if not isinstance(response_data, dict):
            return False
        if response_data.get("status") != "ok":
            return False
        if not isinstance(response_data.get("articles"), list):
            return False
        return True

    def normalize_article(self, raw_item: Dict[str, Any]) -> Optional[NormalizedArticle]:
        """
        Normalize News API article dictionary into standardized NormalizedArticle schema.
        Validates URL safety and sanitizes text.
        """
        try:
            url = raw_item.get("url")
            if not url or not validate_url(url, allow_private=False):
                logger.debug(f"[NewsAPI] Skipping article with invalid or unsafe URL: {url}")
                return None

            title = sanitize_text(raw_item.get("title", ""), max_length=512)
            if not title or title.strip() == "[Removed]":
                return None

            description = sanitize_text(raw_item.get("description"), max_length=2000)
            content = sanitize_text(raw_item.get("content"), max_length=6000)

            # Parse publisher
            source_info = raw_item.get("source", {}) or {}
            publisher_name = sanitize_text(source_info.get("name") or "NewsAPI Publisher", max_length=255)
            
            # Extract domain
            domain = urlparse(url).netloc.lower()

            # Parse publication timestamp
            pub_date_raw = raw_item.get("publishedAt")
            if pub_date_raw:
                try:
                    published_at = date_parser.parse(pub_date_raw)
                    # Convert to naive UTC datetime
                    if published_at.tzinfo:
                        published_at = published_at.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                except Exception:
                    published_at = datetime.datetime.utcnow()
            else:
                published_at = datetime.datetime.utcnow()

            canonical = normalize_url(url)
            art_hash = compute_article_hash(canonical, title)

            image_url = raw_item.get("urlToImage")
            if image_url and not validate_url(image_url, allow_private=False):
                image_url = None

            return NormalizedArticle(
                original_id=raw_item.get("source", {}).get("id") or art_hash[:16],
                title=title,
                description=description,
                content=content,
                url=url,
                canonical_url=canonical,
                article_hash=art_hash,
                image_url=image_url,
                publisher_name=publisher_name,
                publisher_domain=domain,
                author=sanitize_text(raw_item.get("author"), max_length=255),
                published_at=published_at,
                language="en",
                country="us",
                category="General",
                source_type="newsapi",
                raw_metadata=raw_item,
            )
        except Exception as exc:
            self.report_errors(exc, {"raw_item_title": raw_item.get("title")})
            return None

    def get_top_headlines(
        self,
        country: Optional[str] = "us",
        category: Optional[str] = None,
        sources: Optional[str] = None,
        query: Optional[str] = None,
        page_size: int = 20,
        page: int = 1,
    ) -> List[NormalizedArticle]:
        """Fetch top headlines from GET /v2/top-headlines."""
        params = {
            "country": country if not sources else None,
            "category": category if not sources else None,
            "sources": sources,
            "q": query,
            "pageSize": min(page_size, 100),
            "page": page,
        }
        data = self._execute_request("top-headlines", params)
        if not self.validate_response(data):
            return []

        articles: List[NormalizedArticle] = []
        for raw in data.get("articles", []):
            norm = self.normalize_article(raw)
            if norm:
                if category:
                    norm.category = category
                articles.append(norm)
        return articles

    def search_everything(
        self,
        query: str,
        sources: Optional[str] = None,
        domains: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        language: str = "en",
        sort_by: str = "publishedAt",
        page_size: int = 20,
        page: int = 1,
    ) -> List[NormalizedArticle]:
        """Search news articles using GET /v2/everything."""
        params = {
            "q": query,
            "sources": sources,
            "domains": domains,
            "from": from_date,
            "to": to_date,
            "language": language,
            "sortBy": sort_by,
            "pageSize": min(page_size, 100),
            "page": page,
        }
        data = self._execute_request("everything", params)
        if not self.validate_response(data):
            return []

        articles: List[NormalizedArticle] = []
        for raw in data.get("articles", []):
            norm = self.normalize_article(raw)
            if norm:
                articles.append(norm)
        return articles

    def get_sources(
        self,
        category: Optional[str] = None,
        language: Optional[str] = None,
        country: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve available publisher sources from GET /v2/top-headlines/sources."""
        params = {"category": category, "language": language, "country": country}
        data = self._execute_request("top-headlines/sources", params)
        if data.get("status") == "ok":
            return data.get("sources", [])
        return []

    def fetch_articles(self, **kwargs) -> List[NormalizedArticle]:
        """Polymorphic fetch: defaults to top headlines or search query if supplied."""
        q = kwargs.get("q") or kwargs.get("query")
        if q:
            return self.search_everything(
                query=q,
                page_size=kwargs.get("page_size", 20),
                language=kwargs.get("language", "en"),
            )
        return self.get_top_headlines(
            country=kwargs.get("country", "us"),
            category=kwargs.get("category"),
            page_size=kwargs.get("page_size", 20),
        )
