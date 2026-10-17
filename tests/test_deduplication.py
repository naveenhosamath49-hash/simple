from __future__ import annotations

import unittest
from app.connectors.base import normalize_url, compute_article_hash
from app.services.deduplication import DeduplicationService, get_token_shingles, calculate_jaccard_similarity


class TestNormalizationAndDeduplication(unittest.TestCase):
    def setUp(self):
        self.dedup_service = DeduplicationService(threshold=0.80)

    def test_url_normalization(self):
        url1 = "https://WWW.Reuters.COM/technology/ai-update/?utm_source=twitter&utm_medium=social#overview"
        url2 = "https://www.reuters.com/technology/ai-update"
        canon1 = normalize_url(url1)
        canon2 = normalize_url(url2)
        self.assertEqual(canon1, canon2)
        self.assertNotIn("utm_source", canon1)
        self.assertNotIn("#overview", canon1)

    def test_article_hash_exact_duplicate(self):
        url = "https://www.reuters.com/markets/stocks-2026"
        title1 = "Stock Markets Reach Historic Highs in October Trading"
        title2 = "Stock Markets Reach Historic Highs In October Trading "

        hash1 = compute_article_hash(url, title1)
        hash2 = compute_article_hash(url, title2)
        self.assertEqual(hash1, hash2)

    def test_near_duplicate_detection(self):
        title_a = "NVIDIA Expands Enterprise AI Platform With New Microservices"
        body_a = "NVIDIA has announced broader enterprise availability of its NIM microservices suite to accelerate generative models."

        title_b = "NVIDIA Expands Enterprise AI Platform With New Microservice Suite"
        body_b = "NVIDIA announced broader enterprise availability of its NIM microservices suite to accelerate generative models."

        score = self.dedup_service.compute_similarity(title_a, body_a, title_b, body_b)
        self.assertGreaterEqual(score, 0.80)

        existing = [(1, title_a, body_a)]
        match = self.dedup_service.find_near_duplicate(title_b, body_b, existing)
        self.assertIsNotNone(match)
        self.assertEqual(match[0], 1)

    def test_distinct_articles_are_not_duplicates(self):
        title_a = "Federal Reserve Holds Interest Rates Steady"
        body_a = "The central bank decided to maintain the benchmark rate at 5.00 percent following stable inflation data."

        title_b = "Global Leaders Negotiate Treaty on Autonomous Defense Systems"
        body_b = "Diplomats gathered in Geneva to establish international protocols for autonomous weapons systems."

        score = self.dedup_service.compute_similarity(title_a, body_a, title_b, body_b)
        self.assertLess(score, 0.30)

        existing = [(1, title_a, body_a)]
        match = self.dedup_service.find_near_duplicate(title_b, body_b, existing)
        self.assertIsNone(match)

    def test_jaccard_similarity(self):
        set_a = {"apple", "banana", "cherry"}
        set_b = {"apple", "banana", "date"}
        sim = calculate_jaccard_similarity(set_a, set_b)
        self.assertAlmostEqual(sim, 2 / 4)


if __name__ == "__main__":
    unittest.main()
