"""Connectors package for external news ingestion."""
from app.connectors.base import BaseConnector, NormalizedArticle
from app.connectors.news_api import NewsAPIConnector
from app.connectors.rss import RSSConnector

__all__ = [
    "BaseConnector",
    "NormalizedArticle",
    "NewsAPIConnector",
    "RSSConnector",
]
