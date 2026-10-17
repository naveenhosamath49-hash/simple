from __future__ import annotations

import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.database.repository import NewsRepository
from app.database.models import Article


class SearchService:
    """High-level news search and intelligence retrieval service."""

    def __init__(self, db: Session):
        self.repo = NewsRepository(db)

    def search_news(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        publisher: Optional[str] = None,
        source_type: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        days_back: Optional[int] = None,
        min_importance: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Execute multi-facet search across stored news items.
        """
        date_from = None
        if days_back:
            date_from = datetime.datetime.utcnow() - datetime.timedelta(days=days_back)

        offset = max(0, (page - 1) * page_size)
        articles, total_count = self.repo.search_articles(
            query=query,
            category=category,
            publisher=publisher,
            source_type=source_type,
            country=country,
            language=language,
            date_from=date_from,
            min_importance=min_importance,
            limit=page_size,
            offset=offset,
        )

        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

        return {
            "query": query,
            "category": category,
            "total_results": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "articles": [a.to_dict() for a in articles],
        }
