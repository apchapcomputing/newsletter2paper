"""Unit tests for enhanced RSS service functionality."""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import requests
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
from services.rss_service import RSSService


class MockResponse:
    """Mock response object for requests."""
    def __init__(self, text="", status_code=200, headers=None, url=None):
        self.text = text
        self.content = text.encode('utf-8') if text else b""
        self.status_code = status_code
        self.headers = headers or {}
        self.url = url or "https://example.com"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.RequestException(f"HTTP {self.status_code}")


class TestEnhancedFeedDiscovery(unittest.TestCase):
    """Test cases for enhanced RSS feed discovery."""

    def setUp(self):
        """Set up test fixtures."""
        self.rss_service = RSSService()
        self.test_url = "https://example.com"

    def test_is_feed_content_type_rss(self):
        """Test content type detection for RSS feeds."""
        self.assertTrue(self.rss_service._is_feed_content_type("application/rss+xml"))
        self.assertTrue(self.rss_service._is_feed_content_type("application/atom+xml"))
        self.assertTrue(self.rss_service._is_feed_content_type("text/xml"))
        self.assertTrue(self.rss_service._is_feed_content_type("application/xml"))
        
    def test_is_feed_content_type_non_feed(self):
        """Test content type detection for non-feed content."""
        self.assertFalse(self.rss_service._is_feed_content_type("text/html"))
        self.assertFalse(self.rss_service._is_feed_content_type("application/json"))
        self.assertFalse(self.rss_service._is_feed_content_type(""))
        self.assertFalse(self.rss_service._is_feed_content_type(None))

    def test_guess_common_feed_paths(self):
        """Test common feed path generation."""
        from urllib.parse import urlparse
        parsed_url = urlparse("https://example.com/blog")
        paths = self.rss_service._guess_common_feed_paths(parsed_url)
        
        expected_paths = [
            "https://example.com/feed",
            "https://example.com/rss",
            "https://example.com/rss.xml",
            "https://example.com/atom.xml",
            "https://example.com/feeds/posts/default",
            "https://example.com/feeds",
            "https://example.com/feed.xml",
            "https://example.com/index.xml"
        ]
        
        self.assertEqual(paths, expected_paths)

    @patch('requests.head')
    @patch('requests.get')
    def test_get_feed_url_direct_feed(self, mock_get, mock_head):
        """Test feed discovery when URL is already a feed."""
        # Mock HEAD request to return feed content type
        mock_head.return_value = MockResponse(
            "", 200, 
            {"content-type": "application/rss+xml"}, 
            "https://example.com/feed"
        )
        
        result = self.rss_service.get_feed_url("https://example.com/feed")
        
        self.assertEqual(result, "https://example.com/feed")
        mock_head.assert_called_once()
        mock_get.assert_not_called()

    @patch('requests.head')
    @patch('requests.get')
    def test_get_feed_url_html_with_link_tags(self, mock_get, mock_head):
        """Test feed discovery from HTML with link tags."""
        # Mock HEAD requests: first for main page fails, second for candidate succeeds
        def head_side_effect(url, **kwargs):
            if 'feed.xml' in url:
                # Return feed content-type for the candidate
                return MockResponse("", 200, {"content-type": "application/rss+xml"}, url=url)
            raise requests.RequestException("HEAD not allowed")
        
        mock_head.side_effect = head_side_effect
        
        # Mock GET request returns HTML with feed link
        html_content = '''
        <html>
        <head>
            <link rel="alternate" type="application/rss+xml" href="/feed.xml" />
        </head>
        <body>Content</body>
        </html>
        '''
        mock_get.return_value = MockResponse(html_content, 200, {"content-type": "text/html"})
        
        result = self.rss_service.get_feed_url(self.test_url)
        
        self.assertEqual(result, "https://example.com/feed.xml")

    @patch('requests.head')
    @patch('requests.get')
    def test_get_feed_url_common_paths(self, mock_get, mock_head):
        """Test feed discovery using common paths."""
        # Mock HEAD request fails
        mock_head.side_effect = [
            requests.RequestException("HEAD not allowed"),
            MockResponse("", 200, {"content-type": "application/rss+xml"}, "https://example.com/feed")
        ]
        
        # Mock GET request returns HTML without feed links
        html_content = '<html><head></head><body>Content</body></html>'
        mock_get.return_value = MockResponse(html_content, 200, {"content-type": "text/html"})
        
        result = self.rss_service.get_feed_url(self.test_url)
        
        self.assertEqual(result, "https://example.com/feed")

    @patch('requests.head')
    @patch('requests.get')
    def test_get_feed_url_not_found(self, mock_get, mock_head):
        """Test feed discovery when no feed is found."""
        # Mock all requests to fail or return non-feed content
        mock_head.side_effect = requests.RequestException("HEAD not allowed")
        mock_get.return_value = MockResponse(
            '<html><head></head><body>Content</body></html>', 
            200, 
            {"content-type": "text/html"}
        )
        
        result = self.rss_service.get_feed_url(self.test_url)
        
        self.assertIsNone(result)

    def test_get_feed_url_adds_protocol(self):
        """Test that protocol is added to URLs without it."""
        with patch('requests.head') as mock_head:
            mock_head.return_value = MockResponse(
                "", 200, 
                {"content-type": "application/rss+xml"}, 
                "https://example.com/feed"
            )
            
            result = self.rss_service.get_feed_url("example.com")
            
            mock_head.assert_called_once()
            # Verify the call was made with https:// prefix
            args, kwargs = mock_head.call_args
            self.assertTrue(args[0].startswith("https://"))


class TestRSSParsingUtilities(unittest.TestCase):
    """Test cases for RSS parsing utilities."""

    def setUp(self):
        """Set up test fixtures."""
        self.rss_service = RSSService()

    def test_validate_rss_content_valid_rss(self):
        """Test RSS content validation with valid RSS."""
        valid_rss = '''<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item><title>Test Item</title></item>
            </channel>
        </rss>'''
        
        self.assertTrue(self.rss_service.validate_rss_content(valid_rss))

    def test_validate_rss_content_valid_atom(self):
        """Test RSS content validation with valid Atom."""
        valid_atom = '''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Test Feed</title>
            <entry><title>Test Entry</title></entry>
        </feed>'''
        
        self.assertTrue(self.rss_service.validate_rss_content(valid_atom))

    def test_validate_rss_content_invalid_xml(self):
        """Test RSS content validation with invalid XML."""
        invalid_xml = "<html><body>Not XML</body></html>"
        
        self.assertFalse(self.rss_service.validate_rss_content(invalid_xml))

    def test_validate_rss_content_malformed(self):
        """Test RSS content validation with malformed XML."""
        malformed_xml = "<?xml version='1.0'?><rss><channel><item></rss>"
        
        self.assertFalse(self.rss_service.validate_rss_content(malformed_xml))

    def test_extract_feed_info(self):
        """Test feed information extraction."""
        rss_content = '''<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <description>A test RSS feed</description>
                <link>https://example.com</link>
                <item><title>Item 1</title></item>
                <item><title>Item 2</title></item>
            </channel>
        </rss>'''
        
        info = self.rss_service.extract_feed_info(rss_content)
        
        self.assertEqual(info['title'], 'Test Feed')
        self.assertEqual(info['description'], 'A test RSS feed')
        self.assertEqual(info['link'], 'https://example.com')
        self.assertEqual(info['item_count'], 2)

    def test_extract_feed_info_minimal(self):
        """Test feed information extraction with minimal content."""
        rss_content = '''<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
            </channel>
        </rss>'''
        
        info = self.rss_service.extract_feed_info(rss_content)
        
        self.assertEqual(info['title'], 'unknown_feed')
        self.assertEqual(info['description'], '')
        self.assertEqual(info['link'], '')
        self.assertEqual(info['item_count'], 0)

    def test_parse_rss_date_rfc2822(self):
        """Test RSS date parsing with RFC 2822 format."""
        date_str = "Wed, 07 Aug 2025 14:41:57 +0000"
        
        result = self.rss_service.parse_rss_date(date_str)
        
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 8)
        self.assertEqual(result.day, 7)

    def test_parse_rss_date_iso_format(self):
        """Test RSS date parsing with ISO format."""
        date_str = "2025-08-07T14:41:57Z"
        
        result = self.rss_service.parse_rss_date(date_str)
        
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 8)
        self.assertEqual(result.day, 7)

    def test_parse_rss_date_invalid(self):
        """Test RSS date parsing with invalid date."""
        invalid_dates = ["invalid date", "", None, "2025-13-45"]
        
        for date_str in invalid_dates:
            result = self.rss_service.parse_rss_date(date_str)
            self.assertIsNone(result)


class TestDateFilteringUtilities(unittest.TestCase):
    """Test cases for date filtering utilities."""

    def setUp(self):
        """Set up test fixtures."""
        self.rss_service = RSSService()
        
        # Create sample articles with different dates
        self.sample_articles = [
            {
                'title': 'Recent Article',
                'pub_date': 'Wed, 01 Oct 2025 14:00:00 +0000'
            },
            {
                'title': 'Week Old Article',
                'pub_date': 'Wed, 24 Sep 2025 14:00:00 +0000'
            },
            {
                'title': 'Month Old Article',
                'pub_date': 'Wed, 01 Sep 2025 14:00:00 +0000'
            },
            {
                'title': 'Invalid Date Article',
                'pub_date': 'invalid date'
            }
        ]

    def test_filter_articles_by_date_no_filters(self):
        """Test article filtering with no date filters."""
        result = self.rss_service.filter_articles_by_date(self.sample_articles)
        
        self.assertEqual(len(result), len(self.sample_articles))

    def test_filter_articles_by_date_start_date(self):
        """Test article filtering with start date."""
        start_date = datetime(2025, 9, 25)
        
        result = self.rss_service.filter_articles_by_date(
            self.sample_articles, 
            start_date=start_date
        )
        
        # Should include recent article, exclude month old
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'Recent Article')

    def test_filter_articles_by_date_end_date(self):
        """Test article filtering with end date."""
        end_date = datetime(2025, 9, 25)
        
        result = self.rss_service.filter_articles_by_date(
            self.sample_articles, 
            end_date=end_date
        )
        
        # Should include week old and month old, exclude recent
        self.assertEqual(len(result), 2)

    def test_get_date_range_for_period_last_week(self):
        """Test date range calculation for last week."""
        start_date, end_date = self.rss_service.get_date_range_for_period('last-week')
        
        now = datetime.now()
        expected_start = now - timedelta(days=7)
        
        self.assertAlmostEqual(
            start_date.timestamp(), 
            expected_start.timestamp(), 
            delta=60  # Within 1 minute
        )
        self.assertAlmostEqual(
            end_date.timestamp(), 
            now.timestamp(), 
            delta=60
        )

    def test_get_date_range_for_period_last_month(self):
        """Test date range calculation for last month."""
        start_date, end_date = self.rss_service.get_date_range_for_period('last-month')
        
        now = datetime.now()
        expected_start = now - timedelta(days=30)
        
        self.assertAlmostEqual(
            start_date.timestamp(), 
            expected_start.timestamp(), 
            delta=60
        )

    def test_get_date_range_for_period_custom_range(self):
        """Test date range calculation for custom date range."""
        start_date, end_date = self.rss_service.get_date_range_for_period(
            '2025-01-01,2025-01-31'
        )
        
        self.assertEqual(start_date, datetime(2025, 1, 1))
        self.assertEqual(end_date, datetime(2025, 1, 31))

    def test_get_date_range_for_period_invalid(self):
        """Test date range calculation with invalid period."""
        with self.assertRaises(ValueError):
            self.rss_service.get_date_range_for_period('invalid-period')
        
        with self.assertRaises(ValueError):
            self.rss_service.get_date_range_for_period('2025-13-01,2025-01-31')


if __name__ == '__main__':
    unittest.main()