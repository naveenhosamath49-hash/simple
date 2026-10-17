from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
import httpx
from app.connectors.news_api import NewsAPIConnector
from app.connectors.rss import RSSConnector, strip_html_tags


class TestNewsAPIConnector(unittest.TestCase):
    def setUp(self):
        self.connector = NewsAPIConnector(api_key="test-api-key")

    def test_missing_api_key(self):
        empty_connector = NewsAPIConnector(api_key="")
        res = empty_connector.fetch_articles()
        self.assertEqual(res, [])

    @patch("httpx.Client.get")
    def test_successful_top_headlines(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"X-RateLimit-Remaining": "99"}
        mock_resp.json.return_value = {
            "status": "ok",
            "totalResults": 1,
            "articles": [
                {
                    "source": {"id": "wired", "name": "Wired"},
                    "author": "Tech Reporter",
                    "title": "Quantum Leap in AI Chips",
                    "description": "Chipmaker reveals ultra-fast tensor architecture.",
                    "url": "https://www.wired.com/story/quantum-leap-ai-chips",
                    "urlToImage": "https://www.wired.com/image.jpg",
                    "publishedAt": "2026-10-14T08:00:00Z",
                    "content": "Full article text discussing next gen architecture.",
                }
            ],
        }
        mock_get.return_value = mock_resp

        articles = self.connector.get_top_headlines(country="us")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Quantum Leap in AI Chips")
        self.assertEqual(articles[0].publisher_name, "Wired")
        self.assertEqual(articles[0].publisher_domain, "www.wired.com")

    @patch("httpx.Client.get")
    def test_invalid_api_key_401(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        articles = self.connector.get_top_headlines()
        self.assertEqual(articles, [])

    @patch("httpx.Client.get")
    def test_rate_limited_429(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        # Set max_retries=1 for fast test
        fast_connector = NewsAPIConnector(api_key="test-key", max_retries=1)
        articles = fast_connector.get_top_headlines()
        self.assertEqual(articles, [])

    @patch("httpx.Client.get")
    def test_network_timeout(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("Connection timed out")
        fast_connector = NewsAPIConnector(api_key="test-key", max_retries=1)
        articles = fast_connector.get_top_headlines()
        self.assertEqual(articles, [])

    @patch("httpx.Client.get")
    def test_malformed_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {"status": "error", "message": "Malformed payload"}
        mock_get.return_value = mock_resp

        articles = self.connector.get_top_headlines()
        self.assertEqual(articles, [])

    @patch("httpx.Client.get")
    def test_search_everything(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "source": {"name": "Reuters"},
                    "title": "Global Markets Rally",
                    "description": "Stock indices climbed higher today.",
                    "url": "https://www.reuters.com/markets/rally",
                    "publishedAt": "2026-10-14T09:00:00Z",
                }
            ],
        }
        mock_get.return_value = mock_resp

        results = self.connector.search_everything(query="markets")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].publisher_name, "Reuters")


class TestRSSConnector(unittest.TestCase):
    def test_strip_html_tags(self):
        raw = "<p>This is a <b>bold</b> article summary with an <a href='https://example.com'>external link</a>.</p>"
        cleaned = strip_html_tags(raw)
        self.assertEqual(cleaned, "This is a bold article summary with an external link.")

    @patch("feedparser.parse")
    def test_successful_rss_feed_parsing(self, mock_parse):
        mock_feed = MagicMock()
        mock_feed.entries = [
            {
                "title": "Solar Energy Capacity Surpasses Forecasts",
                "summary": "<p>Renewable power additions hit a new record.</p>",
                "link": "https://www.bbc.com/news/science-solar-2026",
                "published": "Tue, 14 Oct 2026 07:00:00 GMT",
                "author": "Science Correspondent",
            }
        ]
        mock_parse.return_value = mock_feed

        connector = RSSConnector(feeds=[{"name": "BBC Science", "url": "https://feeds.bbci.co.uk/science", "category": "Science"}])
        articles = connector.fetch_feed(connector.feeds[0])

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Solar Energy Capacity Surpasses Forecasts")
        self.assertEqual(articles[0].category, "Science")
        self.assertEqual(articles[0].publisher_name, "BBC Science")
        self.assertNotIn("<p>", articles[0].description)

    @patch("feedparser.parse")
    def test_malformed_feed_with_no_entries(self, mock_parse):
        mock_feed = MagicMock()
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        connector = RSSConnector(feeds=[{"name": "Empty Feed", "url": "https://example.com/rss"}])
        articles = connector.fetch_feed(connector.feeds[0])
        self.assertEqual(articles, [])


if __name__ == "__main__":
    unittest.main()
