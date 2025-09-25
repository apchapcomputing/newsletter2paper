"""Unit tests for RSS feed extraction functionality."""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import os
from datetime import datetime
from pathlib import Path
import asyncio
from services.rss_service import RSSService
from services.database_service import DatabaseService


class MockResponse:
    """Mock response object for requests."""
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
        self.headers = {'content-type': 'application/xml'}

    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception(f"HTTP Status: {self.status_code}")


class TestFeedExtraction(unittest.TestCase):
    """Test cases for RSS feed extraction."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        # Read the sample XML file
        data_dir = Path(__file__).parent.parent.parent / 'data'
        xml_path = data_dir / 'kyla.xml'
        with open(xml_path, 'r', encoding='utf-8') as f:
            cls.sample_xml = f.read()

    def setUp(self):
        """Set up test fixtures before each test."""
        self.rss_service = RSSService()
        self.feed_url = "https://kyla.substack.com/feed"
        
        # Mock the database service
        self.mock_db = MagicMock()
        mock_publication = {
            'id': '08945b32-305a-467e-8117-b4390a47d981',
            'title': "Kyla's Newsletter",
            'url': 'https://kyla.substack.com',
            'feed_url': self.feed_url,
            'publisher': 'Kyla Scanlon'
        }
        
        # Create async mock for database methods
        self.mock_db.get_publication_by_url = AsyncMock(return_value=mock_publication)
        self.mock_db.query_articles_table = AsyncMock(return_value=None)
        self.rss_service.db = self.mock_db

    def asyncSetUp(self):
        """Set up async test fixtures."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def asyncTearDown(self):
        """Clean up async test fixtures."""
        self.loop.close()

    def async_test(func):
        """Decorator for async test methods."""
        def wrapper(*args, **kwargs):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(func(*args, **kwargs))
            finally:
                loop.close()
        return wrapper

    @patch('requests.get')
    @async_test
    async def test_get_articles(self, mock_get):
        """Test extracting articles from a feed."""
        # Configure the mock
        mock_get.return_value = MockResponse(self.sample_xml)

        # Get articles with default pagination
        articles, total = await self.rss_service.get_articles(self.feed_url)

        # Basic assertions
        self.assertIsNotNone(articles)
        self.assertIsInstance(articles, list)
        self.assertTrue(len(articles) > 0)
        self.assertIsInstance(total, int)
        self.assertTrue(total >= len(articles))

        # Check the first article
        first_article = articles[0]
        self.assertEqual(
            first_article.title,
            "How AI, Healthcare, and Labubu Became the American Economy"
        )
        self.assertEqual(first_article.author, "kyla scanlon")
        self.assertEqual(
            first_article.content_url,
            "https://kyla.substack.com/p/how-ai-healthcare-and-labubu-became"
        )
        # Check publication date (August 7, 2025)
        expected_date = datetime(2025, 8, 7, 14, 41, 57)
        self.assertEqual(
            first_article.date_published.replace(tzinfo=None),
            expected_date
        )
        
        # Check subtitle/description extraction
        self.assertIsNotNone(first_article.subtitle)
        self.assertLessEqual(len(first_article.subtitle), 255)
        
        # Check publication linking
        self.assertEqual(
            str(first_article.publication_id),
            '08945b32-305a-467e-8117-b4390a47d981'
        )
        
    @patch('requests.get')
    @async_test
    async def test_pagination(self, mock_get):
        """Test pagination of articles."""
        # Configure the mock
        mock_get.return_value = MockResponse(self.sample_xml)
        
        # Test different pagination scenarios
        test_cases = [
            {"skip": 0, "limit": 5},
            {"skip": 5, "limit": 5},
            {"skip": 0, "limit": 100},
            {"skip": 100, "limit": 10},  # Should return empty list if skip > total
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                articles, total = await self.rss_service.get_articles(
                    self.feed_url,
                    skip=case["skip"],
                    limit=case["limit"]
                )
                
                # Verify pagination constraints
                self.assertLessEqual(len(articles), case["limit"])
                if articles:
                    self.assertGreaterEqual(total, len(articles))

    @async_test
    async def test_live_feed_fetch(self):
        """Test that we can fetch real XML content from the live RSS feed."""
        try:
            import requests
            response = requests.get(
                self.feed_url,
                headers={
                    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                                'AppleWebKit/537.36 (KHTML, like Gecko) '
                                'Chrome/91.0.4472.124 Safari/537.36')
                },
                timeout=30
            )
            response.raise_for_status()
            
            # Check that we got an XML response
            content_type = response.headers.get('content-type', '').lower()
            self.assertTrue(
                any(ct in content_type for ct in ['xml', 'rss', 'atom']),
                f"Expected XML content type, got: {content_type}"
            )
            
            # Check that the content is valid XML
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)
            
            # Verify basic RSS/Atom structure
            channel = root.find('.//channel')
            items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            self.assertTrue(
                len(items) > 0,
                "Expected at least one article in the feed"
            )
            
        except requests.RequestException as e:
            self.skipTest(f"Skipping live feed test - could not reach {self.feed_url}: {str(e)}")
        except ET.ParseError as e:
            self.fail(f"Received invalid XML from feed: {str(e)}")

    @patch('requests.get')
    @async_test
    async def test_error_handling(self, mock_get):
        """Test handling of request errors."""
        # Configure mock to raise an exception
        mock_get.return_value = MockResponse("", status_code=404)

        # Verify that the error is propagated
        with self.assertRaises(Exception):
            await self.rss_service.get_articles(self.feed_url, skip=0, limit=10)

    @patch('requests.get')
    @async_test
    async def test_required_fields(self, mock_get):
        """Test that all required fields are present in parsed articles."""
        # Configure the mock
        mock_get.return_value = MockResponse(self.sample_xml)

        # Get articles
        articles, _ = await self.rss_service.get_articles(self.feed_url)

        # Check each article has required fields
        for article in articles:
            self.assertIsNotNone(article.id)
            self.assertIsNotNone(article.title)
            self.assertIsNotNone(article.date_published)
            self.assertIsNotNone(article.author)
            self.assertIsNotNone(article.content_url)
            
            # Check field length constraints
            self.assertTrue(len(article.title) <= 255)
            self.assertTrue(len(article.author) <= 255)
            self.assertTrue(len(article.content_url) <= 512)
            if article.subtitle:
                self.assertTrue(len(article.subtitle) <= 255)
            if article.storage_url:
                self.assertTrue(len(article.storage_url) <= 512)


if __name__ == '__main__':
    unittest.main()