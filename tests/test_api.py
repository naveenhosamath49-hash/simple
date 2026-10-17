from __future__ import annotations

import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool
from app.main import app
from app.database.database import Base, get_db
from app.database.models import Article, AIAnalysis
import datetime

# Setup test DB engine with StaticPool so all threads share the same in-memory DB
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class TestFastAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        cls.client = TestClient(app)

        # Seed sample articles in test DB
        db = TestingSessionLocal()
        art1 = Article(
            article_hash="1" * 64,
            title="Tech Summit 2026",
            description="Leading AI researchers convene.",
            content="Detailed text regarding AI agents and algorithms.",
            url="https://example.com/art1",
            canonical_url="https://example.com/art1",
            publisher_name="TechDaily",
            publisher_domain="example.com",
            published_at=datetime.datetime.utcnow(),
            category="Technology",
            source_type="rss",
            is_duplicate=False,
        )
        art2 = Article(
            article_hash="2" * 64,
            title="Global Climate Accord Reached",
            description="Nations agree on emissions targets.",
            content="The international accord mandates clean energy quotas.",
            url="https://example.com/art2",
            canonical_url="https://example.com/art2",
            publisher_name="GlobalEco",
            publisher_domain="example.com",
            published_at=datetime.datetime.utcnow(),
            category="International News",
            source_type="rss",
            is_duplicate=False,
        )
        db.add(art1)
        db.add(art2)
        db.commit()

        # Add AI analysis to art1
        analysis = AIAnalysis(
            article_id=art1.id,
            summary="Researchers discussed the evolution of multi-agent architectures.",
            entities={"companies": ["Tech Corp"]},
            classification={"primary_category": "Technology"},
            importance_score=8.0,
            model_used="test-llm",
        )
        db.add(analysis)
        db.commit()

        cls.art1_id = art1.id
        cls.art2_id = art2.id
        db.close()

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)

    def test_health_check(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["database_connected"])

    def test_get_news(self):
        resp = self.client.get("/api/news?page=1&page_size=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["total_results"], 2)
        self.assertTrue(len(data["articles"]) >= 2)

    def test_search_news(self):
        resp = self.client.get("/api/news/search?q=Climate")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_results"], 1)
        self.assertIn("Climate", data["articles"][0]["title"])

    def test_search_empty_results(self):
        resp = self.client.get("/api/news/search?q=NonExistentKeywordXYZ123")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_results"], 0)
        self.assertEqual(data["articles"], [])

    def test_get_article_by_id(self):
        resp = self.client.get(f"/api/news/{self.art1_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], self.art1_id)
        self.assertIsNotNone(data["ai_analysis"])

    def test_get_article_not_found(self):
        resp = self.client.get("/api/news/999999")
        self.assertEqual(resp.status_code, 404)

    def test_get_categories(self):
        resp = self.client.get("/api/categories")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("supported_categories", data)

    def test_get_trends(self):
        resp = self.client.get("/api/trends")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("trends", data)

    def test_ai_summarize_by_id(self):
        resp = self.client.post("/api/ai/summarize", json={"article_id": self.art1_id})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("summary", data)

    def test_ai_ask_question(self):
        resp = self.client.post("/api/ai/ask", json={"question": "What is happening with climate targets?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("answer", data)
        self.assertIn("citations", data)

    def test_ai_compare_claims(self):
        resp = self.client.post("/api/ai/compare-claims", json={"article_ids": [self.art1_id, self.art2_id]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("supported_by_multiple_sources", data)

    def test_sources_status(self):
        resp = self.client.get("/api/sources/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("connectors", data)
        self.assertIn("RSSConnector", data["connectors"])


if __name__ == "__main__":
    unittest.main()
