from __future__ import annotations

import datetime
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database.database import get_db
from app.database.repository import NewsRepository
from app.database.models import Article
from app.services.ingestion import IngestionService
from app.services.search import SearchService
from app.intelligence.llm_provider import get_llm_provider
from app.intelligence.summarizer import ArticleSummarizer
from app.intelligence.claim_comparator import ClaimComparator
from app.intelligence.qa import QuestionAnsweringEngine

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------

class SummarizeRequest(BaseModel):
    article_id: Optional[int] = Field(None, description="Database ID of article to summarize")
    text: Optional[str] = Field(None, description="Raw text snippet to summarize if article_id not provided")
    title: Optional[str] = Field(None, description="Headline or title")


class AskQuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, description="Inquiry for grounded answering")
    category: Optional[str] = Field(None, description="Optional category filter (e.g. Technology, AI)")
    days_back: Optional[int] = Field(7, ge=1, le=90, description="Temporal window to search evidence")
    limit: int = Field(8, ge=1, le=20, description="Max supporting documents to supply to LLM")


class IngestionRunRequest(BaseModel):
    include_news_api: bool = Field(True, description="Fetch from News API if configured")
    include_rss: bool = Field(True, description="Fetch from configured RSS feeds")
    max_articles: Optional[int] = Field(None, ge=1, le=200, description="Max articles to ingest")
    query: Optional[str] = Field(None, description="Optional keyword query for live search ingestion")


class CompareClaimsRequest(BaseModel):
    article_ids: List[int] = Field(..., min_length=2, max_length=10, description="IDs of 2-10 articles to cross-examine")
    topic_hint: Optional[str] = Field(None, description="Optional topic or event label")


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@router.get("/health", status_code=status.HTTP_200_OK)
def health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """System health check and diagnostic status."""
    repo = NewsRepository(db)
    summary = repo.get_system_summary()
    llm = get_llm_provider()

    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database_connected": True,
        "llm_provider": llm.model_name,
        "llm_live": llm.is_available(),
        "total_articles": summary["total_articles"],
        "last_ingestion": summary["last_collection_time"],
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


@router.get("/api/news")
def get_news(
    category: Optional[str] = None,
    publisher: Optional[str] = None,
    source_type: Optional[str] = None,
    country: Optional[str] = None,
    language: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve paginated list of normalized news articles with filtering."""
    search_svc = SearchService(db)
    return search_svc.search_news(
        category=category,
        publisher=publisher,
        source_type=source_type,
        country=country,
        language=language,
        page=page,
        page_size=page_size,
    )


@router.get("/api/news/search")
def search_news_endpoint(
    q: Optional[str] = Query(None, description="Search keyword query"),
    category: Optional[str] = None,
    publisher: Optional[str] = None,
    days_back: Optional[int] = Query(None, ge=1, le=365),
    min_importance: Optional[float] = Query(None, ge=0.0, le=10.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Search news items by query term, temporal scope, and importance rating."""
    search_svc = SearchService(db)
    return search_svc.search_news(
        query=q,
        category=category,
        publisher=publisher,
        days_back=days_back,
        min_importance=min_importance,
        page=page,
        page_size=page_size,
    )


@router.get("/api/news/{article_id}")
def get_article_by_id(article_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve full details of an article including AI analysis and topic associations."""
    repo = NewsRepository(db)
    article = repo.get_article(article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Article {article_id} not found.")

    data = article.to_dict()
    data["topics"] = [t.to_dict() for t in article.topics]
    return data


@router.get("/api/trends")
def get_trends(
    emerging_only: bool = Query(False, description="Filter for emerging topics only"),
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve trending and emerging topics ranked by multi-source velocity."""
    repo = NewsRepository(db)
    topics = repo.get_trending_topics(limit=limit, emerging_only=emerging_only)
    return {
        "count": len(topics),
        "emerging_only": emerging_only,
        "trends": [t.to_dict() for t in topics],
    }


@router.get("/api/categories")
def get_categories(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """List supported and actively populated news categories."""
    repo = NewsRepository(db)
    summary = repo.get_system_summary()
    return {
        "supported_categories": settings.DEFAULT_CATEGORIES,
        "active_category_counts": summary["categories"],
    }


@router.post("/api/ai/summarize")
def summarize_article(req: SummarizeRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Generate concise AI summary and takeaways for an article or text."""
    repo = NewsRepository(db)
    llm = get_llm_provider()
    summarizer = ArticleSummarizer(llm)

    if req.article_id:
        article = repo.get_article(req.article_id)
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found.")
        # If already analyzed, return cached analysis unless text was explicitly provided
        if article.ai_analysis:
            return {
                "article_id": article.id,
                "title": article.title,
                "summary": article.ai_analysis.summary,
                "tone": "Neutral",
                "cached": True,
                "model_used": article.ai_analysis.model_used,
            }

        res = summarizer.summarize(
            title=article.title,
            content=article.content or article.description or "",
            publisher=article.publisher_name,
        )
        return {
            "article_id": article.id,
            "title": article.title,
            "summary": res["summary"],
            "key_takeaways": res.get("key_takeaways", []),
            "tone": res.get("tone", "Neutral"),
            "cached": False,
            "model_used": llm.model_name,
        }

    if req.text:
        res = summarizer.summarize(
            title=req.title or "Submitted Document",
            content=req.text,
            publisher="User Input",
        )
        return {
            "title": req.title or "Submitted Document",
            "summary": res["summary"],
            "key_takeaways": res.get("key_takeaways", []),
            "tone": res.get("tone", "Neutral"),
            "model_used": llm.model_name,
        }

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must provide either article_id or text.")


@router.post("/api/ai/ask")
def ask_question(req: AskQuestionRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Execute grounded question answering over collected articles."""
    repo = NewsRepository(db)
    llm = get_llm_provider()
    qa_engine = QuestionAnsweringEngine(llm)

    # Search for articles relevant to question terms or category
    date_from = datetime.datetime.utcnow() - datetime.timedelta(days=req.days_back or 7)
    articles, _ = repo.search_articles(
        query=req.question,
        category=req.category,
        date_from=date_from,
        limit=req.limit,
    )

    # If search with full query yielded zero, relax query to broad recent articles
    if not articles:
        articles, _ = repo.search_articles(
            category=req.category,
            date_from=date_from,
            limit=req.limit,
        )

    retrieved_dicts = [a.to_dict() for a in articles]
    answer_result = qa_engine.answer_question(req.question, retrieved_dicts)
    answer_result["model_used"] = llm.model_name
    return answer_result


@router.post("/api/ai/compare-claims")
def compare_claims_endpoint(req: CompareClaimsRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Compare and cross-examine factual claims across 2 to 10 selected articles."""
    repo = NewsRepository(db)
    llm = get_llm_provider()
    comparator = ClaimComparator(llm)

    articles = []
    for art_id in req.article_ids:
        art = repo.get_article(art_id)
        if art:
            articles.append(art.to_dict())

    if len(articles) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 valid article IDs must be retrieved for comparison.",
        )

    comparison = comparator.compare_articles(articles, topic_hint=req.topic_hint or "")
    comparison["model_used"] = llm.model_name
    return comparison


@router.post("/api/ingestion/run")
def trigger_ingestion(req: IngestionRunRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Trigger background news collection and processing pipeline."""
    service = IngestionService(db=db, enable_ai=True)
    results = service.run_pipeline(
        include_news_api=req.include_news_api,
        include_rss=req.include_rss,
        max_articles=req.max_articles,
        query=req.query,
    )
    return {
        "status": "completed",
        "details": results,
    }


@router.get("/api/sources/status")
def get_sources_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Operational status and audit logs of all source connectors."""
    repo = NewsRepository(db)
    summary = repo.get_system_summary()
    recent_logs = repo.get_recent_logs(limit=20)

    newsapi_configured = bool(
        settings.NEWS_API_KEY
        and settings.NEWS_API_KEY.strip()
        and settings.NEWS_API_KEY != "your_news_api_key_here"
    )
    nvidia_configured = bool(
        settings.NVIDIA_API_KEY
        and settings.NVIDIA_API_KEY.strip()
        and settings.NVIDIA_API_KEY != "your_nvidia_api_key_here"
    )

    return {
        "connectors": {
            "NewsAPI": {
                "configured": newsapi_configured,
                "endpoint": settings.NEWS_API_BASE_URL,
                "status": "ONLINE" if newsapi_configured else "KEY_NOT_CONFIGURED",
            },
            "RSSConnector": {
                "configured": True,
                "feeds_count": len(settings.DEFAULT_RSS_FEEDS),
                "status": "ONLINE",
            },
            "NvidiaLLM": {
                "configured": nvidia_configured,
                "model": settings.NVIDIA_MODEL,
                "endpoint": settings.NVIDIA_BASE_URL,
                "status": "ONLINE" if nvidia_configured else "FALLBACK_MOCK_ACTIVE",
            },
        },
        "stats": summary,
        "recent_logs": [log.to_dict() for log in recent_logs],
    }
