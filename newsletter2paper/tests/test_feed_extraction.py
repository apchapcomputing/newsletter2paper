"""RSSService.get_articles against a realistic Substack-shaped feed."""

import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import requests

from services.rss_service import RSSService

FEED_URL = "https://example.substack.com/feed"
PUBLICATION_ID = "08945b32-305a-467e-8117-b4390a47d981"
SAMPLE_XML = (Path(__file__).parent / "fixtures" / "substack_feed.xml").read_text(encoding="utf-8")


class MockResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
        self.headers = {"content-type": "application/xml"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class TestFeedExtraction(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # The feed cache is class-level (shared by per-request instances); isolate each test.
        RSSService._rss_cache.clear()
        self.addCleanup(RSSService._rss_cache.clear)
        self.rss_service = RSSService()
        self.rss_service.db = MagicMock()
        self.rss_service.db.get_publication_by_url = AsyncMock(return_value={"id": PUBLICATION_ID})

    @patch("requests.get")
    async def test_item_fields_are_mapped(self, mock_get):
        mock_get.return_value = MockResponse(SAMPLE_XML)

        articles, total = await self.rss_service.get_articles(FEED_URL)

        self.assertEqual(total, 3)
        newest = articles[0]
        self.assertEqual(newest.title, "Third post: newest")
        self.assertEqual(newest.author, "Ada Writer")
        self.assertEqual(newest.content_url, "https://example.substack.com/p/third-post")
        self.assertEqual(newest.subtitle, "Short blurb for the newest post.")
        self.assertEqual(newest.date_published, datetime(2025, 8, 7, 14, 41, 57, tzinfo=timezone.utc))

    @patch("requests.get")
    async def test_articles_are_linked_to_the_publication_registered_for_the_feed(self, mock_get):
        mock_get.return_value = MockResponse(SAMPLE_XML)

        articles, _ = await self.rss_service.get_articles(FEED_URL)

        self.rss_service.db.get_publication_by_url.assert_awaited_once_with(FEED_URL)
        self.assertEqual({str(a.publication_id) for a in articles}, {PUBLICATION_ID})

    @patch("requests.get")
    async def test_articles_stay_unlinked_when_feed_is_not_a_known_publication(self, mock_get):
        mock_get.return_value = MockResponse(SAMPLE_XML)
        self.rss_service.db.get_publication_by_url = AsyncMock(return_value=None)

        articles, _ = await self.rss_service.get_articles(FEED_URL)

        self.assertTrue(all(a.publication_id is None for a in articles))

    @patch("requests.get")
    async def test_pagination_returns_a_window_but_reports_the_full_total(self, mock_get):
        mock_get.return_value = MockResponse(SAMPLE_XML)

        page, total = await self.rss_service.get_articles(FEED_URL, skip=1, limit=1)

        self.assertEqual(total, 3)
        self.assertEqual([a.title for a in page], ["Second post"])

    @patch("requests.get")
    async def test_skipping_past_the_end_yields_an_empty_page(self, mock_get):
        mock_get.return_value = MockResponse(SAMPLE_XML)

        page, total = await self.rss_service.get_articles(FEED_URL, skip=10, limit=5)

        self.assertEqual((page, total), ([], 3))

    @patch("requests.get")
    async def test_http_error_propagates_to_the_caller(self, mock_get):
        mock_get.return_value = MockResponse("", status_code=404)

        with self.assertRaises(requests.RequestException):
            await self.rss_service.get_articles(FEED_URL)

    @patch("requests.get")
    async def test_repeat_fetches_within_cache_window_hit_the_network_once(self, mock_get):
        mock_get.return_value = MockResponse(SAMPLE_XML)

        await self.rss_service.get_articles(FEED_URL)
        later_request = RSSService()  # a different instance, as each request gets its own
        later_request.db = self.rss_service.db
        await later_request.get_articles(FEED_URL)

        self.assertEqual(mock_get.call_count, 1)

    @patch("requests.get")
    async def test_overlong_fields_are_truncated_to_model_limits(self, mock_get):
        long = "x" * 600
        feed = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title><item>
            <title>{long}</title><description>{long}</description><author>{long}</author>
            <link>https://example.com/{long}</link><pubDate>Thu, 07 Aug 2025 14:41:57 GMT</pubDate>
        </item></channel></rss>"""
        mock_get.return_value = MockResponse(feed)

        (article,), _ = await self.rss_service.get_articles(FEED_URL)

        self.assertEqual(len(article.title), 255)
        self.assertEqual(len(article.subtitle), 255)
        self.assertEqual(len(article.author), 255)
        self.assertEqual(len(article.content_url), 512)


if __name__ == "__main__":
    unittest.main()
