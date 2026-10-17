from __future__ import annotations

import datetime
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.models import Base
from app.database.repository import NewsRepository


class TestDatabaseRepository(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.repo = NewsRepository(self.db)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_insert_and_retrieve_article(self):
        art_dict = {
            "original_id": "test-1",
            "title": "Quantum Computing Reaches Breakthrough",
            "description": "Researchers stabilize physical qubits.",
            "content": "Full detailed article text.",
            "url": "https://example.com/quantum",
            "canonical_url": "https://example.com/quantum",
            "article_hash": "a" * 64,
            "publisher_name": "Tech Times",
            "publisher_domain": "example.com",
            "published_at": datetime.datetime.utcnow(),
            "category": "Science",
            "language": "en",
            "country": "us",
        }

        art, was_inserted = self.repo.insert_article(art_dict)
        self.assertTrue(was_inserted)
        self.assertIsNotNone(art.id)

        # Lookup by hash
        retrieved = self.repo.get_article_by_hash("a" * 64)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Quantum Computing Reaches Breakthrough")

        # Second insert should return existing and was_inserted=False
        art2, was_inserted2 = self.repo.insert_article(art_dict)
        self.assertFalse(was_inserted2)
        self.assertEqual(art2.id, art.id)

    def test_ai_analysis_persistence(self):
        art_dict = {
            "title": "AI Model Announcement",
            "url": "https://example.com/ai",
            "canonical_url": "https://example.com/ai",
            "article_hash": "b" * 64,
            "publisher_name": "AI Daily",
            "published_at": datetime.datetime.utcnow(),
            "category": "Artificial Intelligence",
        }
        art, _ = self.repo.insert_article(art_dict)

        analysis = self.repo.save_ai_analysis(
            article_id=art.id,
            summary="New state of the art model released.",
            entities={"companies": ["AI Corp"], "people": ["Jane Doe"]},
            classification={"primary_category": "Artificial Intelligence", "confidence": 0.98},
            importance_score=8.5,
            model_used="meta/llama-3.1-70b-instruct",
        )
        self.assertEqual(analysis.article_id, art.id)
        self.assertEqual(analysis.importance_score, 8.5)

        # Retrieve article and verify relationship eager load
        loaded_art = self.repo.get_article(art.id)
        self.assertIsNotNone(loaded_art.ai_analysis)
        self.assertEqual(loaded_art.ai_analysis.summary, "New state of the art model released.")

    def test_topic_creation_and_linking(self):
        art_dict = {
            "title": "Autonomous Defense Treaty",
            "url": "https://example.com/defense",
            "canonical_url": "https://example.com/defense",
            "article_hash": "c" * 64,
            "publisher_name": "Global News",
            "published_at": datetime.datetime.utcnow(),
            "category": "Politics",
        }
        art, _ = self.repo.insert_article(art_dict)

        topic = self.repo.get_or_create_topic("Autonomous Systems")
        self.assertEqual(topic.name, "Autonomous Systems")

        self.repo.link_article_to_topic(art.id, topic.id)
        trending = self.repo.get_trending_topics(limit=5)
        self.assertEqual(len(trending), 1)
        self.assertEqual(trending[0].article_count, 1)

    def test_search_and_filter(self):
        art1 = {
            "title": "Electric Vehicle Sales Surge",
            "description": "Automotive market shifts toward EVs.",
            "url": "https://example.com/ev",
            "canonical_url": "https://example.com/ev",
            "article_hash": "d" * 64,
            "publisher_name": "Auto News",
            "published_at": datetime.datetime.utcnow() - datetime.timedelta(hours=2),
            "category": "Business",
        }
        art2 = {
            "title": "Mars Rover Discovers Mineral Formations",
            "description": "Spectroscopic survey reveals geological history.",
            "url": "https://example.com/mars",
            "canonical_url": "https://example.com/mars",
            "article_hash": "e" * 64,
            "publisher_name": "Space Journal",
            "published_at": datetime.datetime.utcnow() - datetime.timedelta(hours=5),
            "category": "Science",
        }
        self.repo.insert_article(art1)
        self.repo.insert_article(art2)

        # Keyword search
        results, count = self.repo.search_articles(query="Rover")
        self.assertEqual(count, 1)
        self.assertEqual(results[0].title, "Mars Rover Discovers Mineral Formations")

        # Category search
        cat_results, cat_count = self.repo.search_articles(category="Business")
        self.assertEqual(cat_count, 1)
        self.assertEqual(cat_results[0].title, "Electric Vehicle Sales Surge")

    def test_system_logs_and_summary(self):
        self.repo.log_system_event(
            connector_name="RSSConnector",
            operation="fetch",
            status="SUCCESS",
            articles_fetched=10,
            articles_inserted=8,
        )
        logs = self.repo.get_recent_logs(limit=5)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].connector_name, "RSSConnector")

        summary = self.repo.get_system_summary()
        self.assertEqual(summary["last_collection_status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
