from __future__ import annotations

import datetime
import logging
import re
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
import feedparser
from dateutil import parser as date_parser

from app.config import settings
from app.connectors.base import BaseConnector, NormalizedArticle, normalize_url, compute_article_hash
from app.security.validation import validate_url, sanitize_text

logger = logging.getLogger(__name__)


def strip_html_tags(text: Optional[str]) -> str:
    """Remove HTML formatting and scripts from RSS summary strings."""
    if not text:
        return ""
    # Remove script and style elements
    text = re.sub(r"<(script|style).*?>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Unescape common entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    # Clean whitespace before punctuation
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


class RSSConnector(BaseConnector):
    """
    Syndication feed connector parsing RSS 2.0 and Atom feeds.
    Provides immediate news ingestion capabilities even without proprietary API keys.
    """

    def __init__(self, feeds: Optional[List[Dict[str, Any]]] = None):
        super().__init__(name="RSSFeedConnector")
        self.feeds = feeds or settings.DEFAULT_RSS_FEEDS

    def validate_response(self, response_data: Any) -> bool:
        """Validate feedparser result structure."""
        if not hasattr(response_data, "entries"):
            return False
        # Feedparser sets bozo=1 on malformed XML, but entries might still be partially readable
        return True

    def normalize_article(self, raw_item: Dict[str, Any]) -> Optional[NormalizedArticle]:
        """Convert a feedparser entry dict into a NormalizedArticle."""
        try:
            link = raw_item.get("link")
            if not link or not validate_url(link, allow_private=False):
                return None

            raw_title = raw_item.get("title", "")
            title = sanitize_text(strip_html_tags(raw_title), max_length=512)
            if not title:
                return None

            raw_summary = raw_item.get("summary") or raw_item.get("description") or ""
            description = sanitize_text(strip_html_tags(raw_summary), max_length=2000)

            # Try content if available
            content = description
            content_list = raw_item.get("content")
            if content_list and isinstance(content_list, list) and len(content_list) > 0:
                raw_c = content_list[0].get("value", "")
                content = sanitize_text(strip_html_tags(raw_c), max_length=6000)

            # Publication date parsing
            published_at = datetime.datetime.utcnow()
            for date_key in ("published", "pubDate", "updated", "created"):
                if raw_item.get(date_key):
                    try:
                        parsed_dt = date_parser.parse(raw_item[date_key])
                        if parsed_dt.tzinfo:
                            parsed_dt = parsed_dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                        published_at = parsed_dt
                        break
                    except Exception:
                        continue

            canonical = normalize_url(link)
            art_hash = compute_article_hash(canonical, title)

            # Publisher info from feed context
            publisher_name = raw_item.get("feed_name") or "RSS Publisher"
            domain = urlparse(link).netloc.lower()

            # Image extraction from enclosures or media_content
            image_url = None
            enclosures = raw_item.get("enclosures") or []
            for enc in enclosures:
                if enc.get("type", "").startswith("image/") and enc.get("href"):
                    if validate_url(enc["href"], allow_private=False):
                        image_url = enc["href"]
                        break

            if not image_url and "media_content" in raw_item:
                media = raw_item.get("media_content") or []
                if media and isinstance(media, list) and "url" in media[0]:
                    m_url = media[0]["url"]
                    if validate_url(m_url, allow_private=False):
                        image_url = m_url

            author = sanitize_text(raw_item.get("author"), max_length=255)
            category = raw_item.get("feed_category") or "General"

            return NormalizedArticle(
                original_id=raw_item.get("id") or art_hash[:16],
                title=title,
                description=description,
                content=content,
                url=link,
                canonical_url=canonical,
                article_hash=art_hash,
                image_url=image_url,
                publisher_name=publisher_name,
                publisher_domain=domain,
                author=author,
                published_at=published_at,
                language=raw_item.get("feed_language", "en"),
                country=raw_item.get("feed_country", "us"),
                category=category,
                source_type="rss",
                raw_metadata={"tags": [t.get("term") for t in raw_item.get("tags", []) if isinstance(t, dict)]},
            )
        except Exception as exc:
            self.report_errors(exc, {"entry_title": raw_item.get("title")})
            return None

    def fetch_feed(self, feed_cfg: Dict[str, Any], limit: int = 20) -> List[NormalizedArticle]:
        """Fetch and parse a single RSS feed endpoint."""
        feed_url = feed_cfg.get("url")
        if not feed_url or not validate_url(feed_url, allow_private=False):
            logger.warning(f"[RSSConnector] Unsafe or invalid feed URL: {feed_url}")
            return []

        try:
            parsed = feedparser.parse(feed_url)
            if not self.validate_response(parsed):
                return []

            articles: List[NormalizedArticle] = []
            for entry in parsed.entries[:limit]:
                # Inject feed metadata
                entry_dict = dict(entry)
                entry_dict["feed_name"] = feed_cfg.get("name")
                entry_dict["feed_category"] = feed_cfg.get("category", "General")
                entry_dict["feed_language"] = feed_cfg.get("language", "en")
                entry_dict["feed_country"] = feed_cfg.get("country", "us")

                norm = self.normalize_article(entry_dict)
                if norm:
                    articles.append(norm)

            logger.info(f"[RSSConnector] Fetched {len(articles)} articles from '{feed_cfg.get('name')}'.")
            return articles
        except Exception as exc:
            self.report_errors(exc, {"feed": feed_cfg.get("name"), "url": feed_url})
            return []

    def fetch_articles(self, **kwargs) -> List[NormalizedArticle]:
        """Fetch articles across all configured RSS channels."""
        limit_per_feed = kwargs.get("limit_per_feed", 15)
        all_articles: List[NormalizedArticle] = []

        for feed_cfg in self.feeds:
            articles = self.fetch_feed(feed_cfg, limit=limit_per_feed)
            all_articles.extend(articles)

        return all_articles
