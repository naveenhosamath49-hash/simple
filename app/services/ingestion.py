from __future__ import annotations

import datetime
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.connectors.base import NormalizedArticle
from app.connectors.news_api import NewsAPIConnector
from app.connectors.rss import RSSConnector
from app.database.repository import NewsRepository
from app.database.models import Article
from app.services.deduplication import DeduplicationService
from app.intelligence.llm_provider import get_llm_provider
from app.intelligence.summarizer import ArticleSummarizer
from app.intelligence.classifier import NewsClassifier
from app.intelligence.entity_extractor import EntityExtractor
from app.intelligence.trend_analyzer import TrendAnalyzer

logger = logging.getLogger(__name__)


class IngestionService:
    """
    End-to-end news ingestion orchestration service:
    Fetches -> Validates -> Normalizes -> Exact Dedup -> Near Dedup -> Persists -> Runs AI Intelligence.
    """

    def __init__(self, db: Session, enable_ai: bool = True):
        self.db = db
        self.repo = NewsRepository(db)
        self.dedup = DeduplicationService()
        self.trend_analyzer = TrendAnalyzer()
        self.enable_ai = enable_ai

        # Initialize connectors
        self.news_api_connector = NewsAPIConnector()
        self.rss_connector = RSSConnector()

        # Initialize AI intelligence components
        self.llm = get_llm_provider()
        self.summarizer = ArticleSummarizer(self.llm)
        self.classifier = NewsClassifier(self.llm)
        self.entity_extractor = EntityExtractor(self.llm)

    def run_pipeline(
        self,
        include_news_api: bool = True,
        include_rss: bool = True,
        max_articles: Optional[int] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute full ingestion cycle across enabled connectors.
        """
        max_items = max_articles or settings.MAX_ARTICLES_PER_FETCH
        all_incoming: List[NormalizedArticle] = []
        stats = {
            "started_at": datetime.datetime.utcnow().isoformat(),
            "fetched": 0,
            "inserted": 0,
            "exact_duplicates": 0,
            "near_duplicates": 0,
            "ai_processed": 0,
            "connectors": {},
        }

        # 1. Fetch from News API
        if include_news_api:
            try:
                if self.news_api_connector.is_configured():
                    logger.info("[Ingestion] Fetching articles from NewsAPI...")
                    newsapi_arts = self.news_api_connector.fetch_articles(q=query, page_size=min(max_items, 30))
                    all_incoming.extend(newsapi_arts)
                    stats["connectors"]["NewsAPI"] = {"status": "SUCCESS", "count": len(newsapi_arts)}
                    self.repo.log_system_event(
                        connector_name="NewsAPI",
                        operation="fetch_articles",
                        status="SUCCESS",
                        articles_fetched=len(newsapi_arts),
                    )
                else:
                    logger.info("[Ingestion] NewsAPI key not configured; skipping NewsAPI connector.")
                    stats["connectors"]["NewsAPI"] = {"status": "SKIPPED", "reason": "No API key configured"}
                    self.repo.log_system_event(
                        connector_name="NewsAPI",
                        operation="fetch_articles",
                        status="SKIPPED",
                        error_details="NEWS_API_KEY missing from environment",
                    )
            except Exception as exc:
                logger.error(f"[Ingestion] Error with NewsAPI: {exc}")
                stats["connectors"]["NewsAPI"] = {"status": "ERROR", "error": str(exc)}
                self.repo.log_system_event(
                    connector_name="NewsAPI",
                    operation="fetch_articles",
                    status="ERROR",
                    error_details=str(exc),
                )

        # 2. Fetch from RSS Feeds
        if include_rss:
            try:
                logger.info("[Ingestion] Fetching articles from configured RSS feeds...")
                rss_arts = self.rss_connector.fetch_articles(limit_per_feed=10)
                all_incoming.extend(rss_arts)
                stats["connectors"]["RSS"] = {"status": "SUCCESS", "count": len(rss_arts)}
                self.repo.log_system_event(
                    connector_name="RSS",
                    operation="fetch_articles",
                    status="SUCCESS",
                    articles_fetched=len(rss_arts),
                )
            except Exception as exc:
                logger.error(f"[Ingestion] Error with RSS feeds: {exc}")
                stats["connectors"]["RSS"] = {"status": "ERROR", "error": str(exc)}
                self.repo.log_system_event(
                    connector_name="RSS",
                    operation="fetch_articles",
                    status="ERROR",
                    error_details=str(exc),
                )

        stats["fetched"] = len(all_incoming)
        logger.info(f"[Ingestion] Total articles collected across connectors: {len(all_incoming)}")

        # 3. Retrieve recent existing articles for near-duplicate comparison window (last 72 hours)
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(hours=72)
        existing_rows = (
            self.db.query(Article.id, Article.title, Article.description)
            .filter(Article.published_at >= cutoff_date)
            .all()
        )
        existing_lookup = [(row[0], row[1], row[2] or "") for row in existing_rows]

        # 4. Process articles sequentially
        inserted_articles: List[Article] = []

        for item in all_incoming:
            # Exact duplicate check via unique SHA-256 hash
            existing_art = self.repo.get_article_by_hash(item.article_hash)
            if existing_art:
                stats["exact_duplicates"] += 1
                continue

            # Check if canonical URL already exists
            existing_url = self.repo.get_article_by_canonical_url(item.canonical_url)
            if existing_url:
                stats["exact_duplicates"] += 1
                continue

            # Check near-duplicate similarity against recent articles
            candidate_body = item.description or item.content or ""
            near_dup_result = self.dedup.find_near_duplicate(
                candidate_title=item.title,
                candidate_body=candidate_body,
                existing_articles=existing_lookup,
            )

            is_duplicate = False
            duplicate_of_id = None
            if near_dup_result is not None:
                parent_id, sim_score = near_dup_result
                is_duplicate = True
                duplicate_of_id = parent_id
                stats["near_duplicates"] += 1

            # Insert article record into database
            article_dict = item.to_db_dict()
            article_dict["is_duplicate"] = is_duplicate
            article_dict["duplicate_of_id"] = duplicate_of_id

            article_obj, was_new = self.repo.insert_article(article_dict)
            if was_new:
                stats["inserted"] += 1
                # Add to local lookup window for subsequent candidates in this batch
                existing_lookup.append((article_obj.id, article_obj.title, candidate_body))

                # Only run expensive AI processing on canonical (non-duplicate) articles
                if not is_duplicate:
                    inserted_articles.append(article_obj)

        # 5. Run AI intelligence pipeline on newly inserted canonical articles
        if self.enable_ai:
            for art in inserted_articles:
                try:
                    self._process_article_ai(art)
                    stats["ai_processed"] += 1
                except Exception as exc:
                    logger.error(f"[Ingestion] AI processing failed for article ID {art.id}: {exc}")

        # 6. Recalculate topics and trend metrics
        try:
            self._update_topics_and_trends()
        except Exception as exc:
            logger.error(f"[Ingestion] Failed to update trend metrics: {exc}")

        stats["completed_at"] = datetime.datetime.utcnow().isoformat()
        logger.info(
            f"[Ingestion] Pipeline completed: Fetched={stats['fetched']}, "
            f"Inserted={stats['inserted']}, ExactDupes={stats['exact_duplicates']}, "
            f"NearDupes={stats['near_duplicates']}, AIProcessed={stats['ai_processed']}"
        )
        return stats

    def _process_article_ai(self, article: Article) -> None:
        """Execute summarization, classification, NER, and importance scoring for an article."""
        # 1. Summarization
        summary_result = self.summarizer.summarize(
            title=article.title,
            content=article.content or article.description or "",
            publisher=article.publisher_name,
        )

        # 2. Classification
        class_result = self.classifier.classify(
            title=article.title,
            description=article.description or "",
            content=article.content or "",
        )
        # Update article category if classifier is confident
        if class_result.get("confidence", 0.0) >= 0.70 and class_result.get("category"):
            article.category = class_result["category"]
            self.db.commit()

        # 3. Entity Extraction
        entities_result = self.entity_extractor.extract_entities(
            title=article.title,
            description=article.description or "",
            content=article.content or "",
        )

        # 4. Importance Scoring
        # Find how many articles share similar topic/publisher to estimate source diversity
        importance_info = self.trend_analyzer.calculate_importance(
            published_at=article.published_at,
            publisher_domain=article.publisher_domain,
            independent_sources_count=1,
            title=article.title,
        )

        # 5. Persist AI Analysis
        self.repo.save_ai_analysis(
            article_id=article.id,
            summary=summary_result["summary"],
            entities=entities_result,
            classification=class_result,
            importance_score=importance_info["score"],
            importance_breakdown=importance_info["breakdown"],
            claims=summary_result.get("key_takeaways", []),
            model_used=self.llm.model_name,
        )

    def _update_topics_and_trends(self) -> None:
        """Cluster recent articles and update topic trend scores."""
        recent_articles, _ = self.repo.search_articles(
            date_from=datetime.datetime.utcnow() - datetime.timedelta(hours=48),
            limit=200,
        )
        dict_articles = []
        for a in recent_articles:
            ad = a.to_dict()
            if a.ai_analysis:
                ad["entities"] = a.ai_analysis.entities
            dict_articles.append(ad)

        topic_clusters = self.trend_analyzer.extract_topic_keywords(dict_articles)

        for topic_name, cluster in topic_clusters.items():
            topic_obj = self.repo.get_or_create_topic(topic_name)
            topic_obj.article_count = cluster["article_count"]
            topic_obj.trend_score = cluster["trend_score"]
            topic_obj.is_emerging = cluster["is_emerging"]
            topic_obj.trend_metrics = {
                "velocity": cluster["velocity"],
                "publishers": cluster["publishers"],
                "is_trending": cluster["is_trending"],
            }
            self.db.commit()

            # Link articles
            for sample in cluster.get("sample_articles", []):
                if sample.get("id"):
                    self.repo.link_article_to_topic(sample["id"], topic_obj.id)
