from __future__ import annotations

import datetime
import re
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import func, or_, desc, and_
from sqlalchemy.orm import Session, joinedload
from app.database.models import Article, AIAnalysis, Topic, ArticleTopic, SystemLog


class NewsRepository:
    """Data Access Object pattern for managing articles, AI metadata, topics, and operational logs."""

    def __init__(self, db: Session):
        self.db = db

    def get_article_by_hash(self, article_hash: str) -> Optional[Article]:
        """Lookup article by SHA-256 fingerprint."""
        return self.db.query(Article).filter(Article.article_hash == article_hash).first()

    def get_article_by_canonical_url(self, canonical_url: str) -> Optional[Article]:
        """Lookup article by canonical URL."""
        return self.db.query(Article).filter(Article.canonical_url == canonical_url).first()

    def get_article(self, article_id: int) -> Optional[Article]:
        """Retrieve article by ID with eager loaded AI analysis and topics."""
        return (
            self.db.query(Article)
            .options(joinedload(Article.ai_analysis), joinedload(Article.topics))
            .filter(Article.id == article_id)
            .first()
        )

    def insert_article(self, article_dict: Dict[str, Any]) -> Tuple[Article, bool]:
        """
        Insert an article if not already present.
        Returns (article_instance, was_inserted).
        """
        existing = self.get_article_by_hash(article_dict["article_hash"])
        if existing:
            return existing, False

        # Create new record
        article = Article(**article_dict)
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)
        return article, True

    def mark_as_duplicate(self, duplicate_article_id: int, canonical_article_id: int) -> None:
        """Mark an article as near-duplicate of an existing canonical article."""
        article = self.db.query(Article).filter(Article.id == duplicate_article_id).first()
        if article:
            article.is_duplicate = True
            article.duplicate_of_id = canonical_article_id
            self.db.commit()

    def search_articles(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        publisher: Optional[str] = None,
        source_type: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        date_from: Optional[datetime.datetime] = None,
        date_to: Optional[datetime.datetime] = None,
        min_importance: Optional[float] = None,
        include_duplicates: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Article], int]:
        """
        Query articles with rich multi-criteria filters, full text filtering, and pagination.
        Returns (articles, total_count).
        """
        q = self.db.query(Article).options(joinedload(Article.ai_analysis), joinedload(Article.topics))

        if not include_duplicates:
            q = q.filter(Article.is_duplicate == False)

        if query:
            clean_q = f"%{query.strip()}%"
            q = q.filter(
                or_(
                    Article.title.ilike(clean_q),
                    Article.description.ilike(clean_q),
                    Article.content.ilike(clean_q),
                    Article.publisher_name.ilike(clean_q),
                )
            )

        if category and category.lower() != "all":
            q = q.filter(Article.category.ilike(category))

        if publisher:
            q = q.filter(Article.publisher_name.ilike(f"%{publisher}%"))

        if source_type:
            q = q.filter(Article.source_type == source_type)

        if country:
            q = q.filter(Article.country == country.lower())

        if language:
            q = q.filter(Article.language == language.lower())

        if date_from:
            q = q.filter(Article.published_at >= date_from)

        if date_to:
            q = q.filter(Article.published_at <= date_to)

        if min_importance is not None:
            q = q.join(Article.ai_analysis).filter(AIAnalysis.importance_score >= min_importance)

        total = q.count()
        articles = q.order_by(desc(Article.published_at)).offset(offset).limit(limit).all()
        return articles, total

    def save_ai_analysis(
        self,
        article_id: int,
        summary: str,
        entities: Dict[str, Any],
        classification: Dict[str, Any],
        importance_score: float,
        importance_breakdown: Optional[Dict[str, Any]] = None,
        claims: Optional[List[Dict[str, Any]]] = None,
        model_used: str = "meta/llama-3.1-70b-instruct",
    ) -> AIAnalysis:
        """Upsert AI analysis associated with an article."""
        analysis = self.db.query(AIAnalysis).filter(AIAnalysis.article_id == article_id).first()
        if not analysis:
            analysis = AIAnalysis(
                article_id=article_id,
                summary=summary,
                entities=entities or {},
                classification=classification or {},
                importance_score=importance_score,
                importance_breakdown=importance_breakdown or {},
                claims=claims or [],
                model_used=model_used,
            )
            self.db.add(analysis)
        else:
            analysis.summary = summary
            analysis.entities = entities or {}
            analysis.classification = classification or {}
            analysis.importance_score = importance_score
            analysis.importance_breakdown = importance_breakdown or {}
            analysis.claims = claims or []
            analysis.model_used = model_used

        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def get_or_create_topic(self, topic_name: str) -> Topic:
        """Find or create a topic by normalized name."""
        clean_name = topic_name.strip()
        slug = re.sub(r"[^\w\s-]", "", clean_name).strip().lower()
        slug = re.sub(r"[-\s]+", "-", slug)

        topic = self.db.query(Topic).filter(Topic.slug == slug).first()
        if not topic:
            topic = Topic(
                name=clean_name,
                slug=slug,
                first_observed_at=datetime.datetime.utcnow(),
                last_observed_at=datetime.datetime.utcnow(),
                article_count=1,
                trend_score=1.0,
                is_emerging=False,
            )
            self.db.add(topic)
            self.db.commit()
            self.db.refresh(topic)
        return topic

    def link_article_to_topic(self, article_id: int, topic_id: int) -> None:
        """Establish association between an article and a topic."""
        exists = (
            self.db.query(ArticleTopic)
            .filter(
                ArticleTopic.c.article_id == article_id,
                ArticleTopic.c.topic_id == topic_id,
            )
            .first()
        )
        if not exists:
            stmt = ArticleTopic.insert().values(
                article_id=article_id,
                topic_id=topic_id,
                created_at=datetime.datetime.utcnow(),
            )
            self.db.execute(stmt)

            # Update topic counts and last observed time
            topic = self.db.query(Topic).filter(Topic.id == topic_id).first()
            if topic:
                topic.article_count = self.db.query(ArticleTopic).filter(ArticleTopic.c.topic_id == topic_id).count()
                topic.last_observed_at = datetime.datetime.utcnow()
            self.db.commit()

    def get_trending_topics(self, limit: int = 15, emerging_only: bool = False) -> List[Topic]:
        """Fetch active trending topics sorted by trend score and recent activity."""
        q = self.db.query(Topic)
        if emerging_only:
            q = q.filter(Topic.is_emerging == True)
        return q.order_by(desc(Topic.trend_score), desc(Topic.last_observed_at)).limit(limit).all()

    def log_system_event(
        self,
        connector_name: str,
        operation: str,
        status: str,
        error_details: Optional[str] = None,
        retry_count: int = 0,
        articles_fetched: int = 0,
        articles_inserted: int = 0,
    ) -> SystemLog:
        """Record operational event into system audit logs."""
        log = SystemLog(
            connector_name=connector_name,
            operation=operation,
            status=status,
            error_details=error_details,
            retry_count=retry_count,
            articles_fetched=articles_fetched,
            articles_inserted=articles_inserted,
            timestamp=datetime.datetime.utcnow(),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_recent_logs(self, limit: int = 50) -> List[SystemLog]:
        """Retrieve recent operational logs."""
        return self.db.query(SystemLog).order_by(desc(SystemLog.timestamp)).limit(limit).all()

    def get_system_summary(self) -> Dict[str, Any]:
        """Calculate system-wide statistics for dashboards and health metrics."""
        now = datetime.datetime.utcnow()
        last_24h = now - datetime.timedelta(hours=24)

        total_articles = self.db.query(Article).count()
        canonical_articles = self.db.query(Article).filter(Article.is_duplicate == False).count()
        recent_24h = self.db.query(Article).filter(Article.published_at >= last_24h).count()
        analyzed_count = self.db.query(AIAnalysis).count()

        # Category breakdown
        category_rows = (
            self.db.query(Article.category, func.count(Article.id))
            .filter(Article.is_duplicate == False)
            .group_by(Article.category)
            .all()
        )
        category_counts = {cat: count for cat, count in category_rows if cat}

        # Source breakdown
        source_rows = (
            self.db.query(Article.publisher_name, func.count(Article.id))
            .filter(Article.is_duplicate == False)
            .group_by(Article.publisher_name)
            .order_by(desc(func.count(Article.id)))
            .limit(10)
            .all()
        )
        source_counts = {src: count for src, count in source_rows if src}

        # Last log
        last_log = self.db.query(SystemLog).order_by(desc(SystemLog.timestamp)).first()

        return {
            "total_articles": total_articles,
            "canonical_articles": canonical_articles,
            "duplicate_articles": total_articles - canonical_articles,
            "recent_articles_24h": recent_24h,
            "ai_analyzed_articles": analyzed_count,
            "categories": category_counts,
            "top_publishers": source_counts,
            "last_collection_time": last_log.timestamp.isoformat() if last_log else None,
            "last_collection_status": last_log.status if last_log else "NO_RUNS_YET",
        }
