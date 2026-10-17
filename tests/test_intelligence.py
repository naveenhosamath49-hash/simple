from __future__ import annotations

import datetime
import json
import unittest
from unittest.mock import patch, MagicMock

from app.intelligence.llm_provider import MockLLMProvider, NvidiaLLMProvider
from app.intelligence.summarizer import ArticleSummarizer
from app.intelligence.classifier import NewsClassifier
from app.intelligence.entity_extractor import EntityExtractor
from app.intelligence.trend_analyzer import TrendAnalyzer
from app.intelligence.claim_comparator import ClaimComparator
from app.intelligence.qa import QuestionAnsweringEngine


class TestIntelligenceLayer(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MockLLMProvider()

    def test_mock_llm_provider_generation(self):
        messages = [{"role": "user", "content": "Please analyze this article and return json"}]
        res = self.mock_llm.generate_chat_completion(messages, response_format_json=True)
        data = json.loads(res)
        self.assertIn("summary", data)
        self.assertIn("entities", data)
        self.assertIn("importance_score", data)

    def test_article_summarizer(self):
        summarizer = ArticleSummarizer(self.mock_llm)
        result = summarizer.summarize(
            title="Breakthrough in Solar Panels",
            content="Engineers have demonstrated a pervoskite cell with 34% efficiency.",
            publisher="Energy Review",
        )
        self.assertIn("summary", result)
        self.assertIn("tone", result)
        self.assertTrue(isinstance(result.get("key_takeaways"), list))

    def test_news_classifier(self):
        classifier = NewsClassifier(self.mock_llm)
        result = classifier.classify(
            title="President Signs Landmark Technology Bill into Law",
            description="The bipartisan legislation funds semiconductor manufacturing facilities.",
        )
        self.assertIn("category", result)
        self.assertIn("confidence", result)
        self.assertGreater(result["confidence"], 0.5)

    def test_entity_extractor(self):
        extractor = EntityExtractor(self.mock_llm)
        entities = extractor.extract_entities(
            title="NVIDIA CEO Jensen Huang Speaks at Tech Forum in San Francisco",
            description="The GPU company unveiled its latest compute infrastructure.",
        )
        for cat in ["people", "organizations", "companies", "locations", "events", "products"]:
            self.assertIn(cat, entities)
            self.assertTrue(isinstance(entities[cat], list))

    def test_trend_analyzer_importance_scoring(self):
        analyzer = TrendAnalyzer(observation_window_hours=48)
        now = datetime.datetime.utcnow()

        # Multi-source recent article from reputable domain
        info_high = analyzer.calculate_importance(
            published_at=now - datetime.timedelta(hours=1),
            publisher_domain="reuters.com",
            independent_sources_count=4,
            title="Emergency Economic Summit Reaches Global Trade Treaty",
        )
        self.assertGreaterEqual(info_high["score"], 7.5)
        self.assertIn("breakdown", info_high)

        # Single source old article from unknown domain
        info_low = analyzer.calculate_importance(
            published_at=now - datetime.timedelta(hours=40),
            publisher_domain="obscureblog.info",
            independent_sources_count=1,
            title="Routine local maintenance completed",
        )
        self.assertLess(info_low["score"], info_high["score"])

    def test_trend_analyzer_requires_two_independent_sources(self):
        analyzer = TrendAnalyzer(observation_window_hours=48)
        now = datetime.datetime.utcnow()

        # Topic reported by ONLY ONE source
        single_source_articles = [
            {
                "id": 1,
                "title": "Quantum Sensor Invented by Lab",
                "publisher_name": "Solo Outlet",
                "published_at": now,
                "entities": {"events": ["Quantum Breakthrough"]},
            }
        ]
        clusters_single = analyzer.extract_topic_keywords(single_source_articles)
        for name, cluster in clusters_single.items():
            self.assertFalse(cluster["is_trending"], "Topic should NOT be trending with only 1 source!")

        # Topic reported by TWO independent sources
        multi_source_articles = [
            {
                "id": 1,
                "title": "Quantum Sensor Invented by Lab",
                "publisher_name": "Reuters",
                "published_at": now - datetime.timedelta(hours=1),
                "entities": {"events": ["Quantum Breakthrough"]},
            },
            {
                "id": 2,
                "title": "New Quantum Sensor Surpasses Existing Limits",
                "publisher_name": "BBC News",
                "published_at": now,
                "entities": {"events": ["Quantum Breakthrough"]},
            },
        ]
        clusters_multi = analyzer.extract_topic_keywords(multi_source_articles)
        for name, cluster in clusters_multi.items():
            self.assertTrue(cluster["is_trending"], "Topic should be trending with 2 independent sources!")

    def test_claim_comparator(self):
        comparator = ClaimComparator(self.mock_llm)
        articles = [
            {"title": "Report A on Space Launch", "publisher_name": "Reuters", "url": "https://reuters.com/1"},
            {"title": "Report B on Space Launch", "publisher_name": "BBC", "url": "https://bbc.com/2"},
        ]
        comparison = comparator.compare_articles(articles, topic_hint="Space Launch")
        self.assertIn("supported_by_multiple_sources", comparison)
        self.assertIn("single_source_claims", comparison)
        self.assertIn("conflicting_claims", comparison)
        self.assertIn("unverified_claims", comparison)

    def test_grounded_qa_insufficient_evidence(self):
        qa = QuestionAnsweringEngine(self.mock_llm)
        result = qa.answer_question("What were the financial results of Company XYZ?", retrieved_articles=[])
        self.assertEqual(result["evidence_status"], "INSUFFICIENT")
        self.assertIn("citations", result)
        self.assertEqual(len(result["citations"]), 0)

    def test_grounded_qa_with_evidence(self):
        qa = QuestionAnsweringEngine(self.mock_llm)
        sample_articles = [
            {
                "title": "AI Platform Expansion Announced",
                "publisher_name": "Reuters",
                "published_at": "2026-10-14T10:00:00",
                "url": "https://reuters.com/ai",
                "description": "NVIDIA expanded its enterprise NIM microservice suite.",
            }
        ]
        result = qa.answer_question("What is new in artificial intelligence?", retrieved_articles=sample_articles)
        self.assertIn("answer", result)
        self.assertGreater(len(result["citations"]), 0)
        self.assertEqual(result["citations"][0]["publisher"], "Reuters")

    @patch("httpx.Client.post")
    def test_nvidia_provider_rate_limit_and_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        provider = NvidiaLLMProvider(api_key="nvapi-validkey", max_retries=1)
        with self.assertRaises(RuntimeError):
            provider.generate_chat_completion([{"role": "user", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
