"""Unit tests for enhanced RSS article extraction and utility methods."""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import requests
from datetime import datetime, timezone
from uuid import UUID
from services.rss_service import RSSService


class MockResponse:
    """Mock response object for requests."""
    def __init__(self, text="", status_code=200, headers=None):
        self.text = text
        self.content = text.encode('utf-8') if text else b""
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/xml"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.RequestException(f"HTTP {self.status_code}")


class TestEnhancedContentExtraction(unittest.TestCase):
    """Test cases for enhanced article content extraction."""

    def setUp(self):
        """Set up test fixtures."""
        self.rss_service = RSSService()
        
        # Mock database service
        self.mock_db = MagicMock()
        mock_publication = {
            'id': '08945b32-305a-467e-8117-b4390a47d981',
            'title': "Test Newsletter",
            'url': 'https://example.com',
            'publisher': 'Test Publisher'
        }
        self.mock_db.get_publication_by_url = AsyncMock(return_value=mock_publication)
        self.rss_service.db = self.mock_db

    def create_sample_rss_with_cdata(self):
        """Create sample RSS with CDATA content."""
        return '''<?xml version="1.0"?>
        <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" 
             xmlns:dc="http://purl.org/dc/elements/1.1/">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title><![CDATA[Article with CDATA Title]]></title>
                    <description><![CDATA[This is a <strong>HTML</strong> description with CDATA]]></description>
                    <content:encoded><![CDATA[<p>Full article content with <em>HTML</em> tags</p>]]></content:encoded>
                    <dc:creator><![CDATA[John Doe]]></dc:creator>
                    <pubDate>Wed, 07 Aug 2025 14:41:57 +0000</pubDate>
                    <link>https://example.com/article1</link>
                    <guid>unique-guid-123</guid>
                </item>
            </channel>
        </rss>'''

    def create_sample_atom_feed(self):
        """Create sample Atom feed."""
        return '''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Test Atom Feed</title>
            <entry>
                <title>Atom Article Title</title>
                <summary>Atom article summary</summary>
                <content type="html">Full Atom content</content>
                <author>
                    <name>Jane Smith</name>
                </author>
                <published>2025-08-07T14:41:57Z</published>
                <link rel="alternate" type="text/html" href="https://example.com/atom-article"/>
            </entry>
        </feed>'''

    def create_sample_rss_multiple_content_sources(self):
        """Create RSS with multiple content sources to test fallbacks."""
        return '''<?xml version="1.0"?>
        <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Article with Multiple Content Sources</title>
                    <description>Primary description content</description>
                    <summary>Alternative summary content</summary>
                    <content:encoded>Enhanced content with encoding</content:encoded>
                    <author>Multi Author</author>
                    <pubDate>Wed, 07 Aug 2025 14:41:57 +0000</pubDate>
                    <link>https://example.com/multi-content</link>
                </item>
                <item>
                    <title>Article with Only Summary</title>
                    <summary>Only summary available</summary>
                    <author>Summary Author</author>
                    <pubDate>Wed, 06 Aug 2025 14:41:57 +0000</pubDate>
                    <link>https://example.com/summary-only</link>
                </item>
            </channel>
        </rss>'''

    @patch('services.rss_service.RSSService.fetch_rss_feed_content')
    async def test_get_articles_cdata_handling(self, mock_fetch):
        """Test article extraction with CDATA content."""
        mock_fetch.return_value = self.create_sample_rss_with_cdata()
        
        articles, total = await self.rss_service.get_articles("https://example.com/feed")
        
        self.assertEqual(len(articles), 1)
        self.assertEqual(total, 1)
        
        article = articles[0]
        self.assertEqual(article.title, "Article with CDATA Title")
        self.assertEqual(article.author, "John Doe")
        self.assertIn("Full article content", article.subtitle)
        self.assertEqual(article.content_url, "https://example.com/article1")

    @patch('services.rss_service.RSSService.fetch_rss_feed_content')
    async def test_get_articles_atom_feed(self, mock_fetch):
        """Test article extraction from Atom feed."""
        mock_fetch.return_value = self.create_sample_atom_feed()
        
        articles, total = await self.rss_service.get_articles("https://example.com/feed")
        
        self.assertEqual(len(articles), 1)
        article = articles[0]
        
        self.assertEqual(article.title, "Atom Article Title")
        self.assertEqual(article.author, "Jane Smith")
        self.assertEqual(article.subtitle, "Full Atom content")
        self.assertEqual(article.content_url, "https://example.com/atom-article")

    @patch('services.rss_service.RSSService.fetch_rss_feed_content')
    async def test_get_articles_content_source_fallback(self, mock_fetch):
        """Test content source fallback logic."""
        mock_fetch.return_value = self.create_sample_rss_multiple_content_sources()
        
        articles, total = await self.rss_service.get_articles("https://example.com/feed")
        
        self.assertEqual(len(articles), 2)
        
        # First article should use content:encoded
        first_article = articles[0]
        self.assertEqual(first_article.subtitle, "Enhanced content with encoding")
        
        # Second article should fallback to summary
        second_article = articles[1]
        self.assertEqual(second_article.subtitle, "Only summary available")

    @patch('services.rss_service.RSSService.fetch_rss_feed_content')
    async def test_get_articles_timezone_handling(self, mock_fetch):
        """Test proper timezone handling for article dates."""
        mock_fetch.return_value = self.create_sample_rss_with_cdata()
        
        articles, total = await self.rss_service.get_articles("https://example.com/feed")
        
        article = articles[0]
        self.assertIsNotNone(article.date_published.tzinfo)
        self.assertEqual(article.date_published.tzinfo, timezone.utc)

    @patch('services.rss_service.RSSService.fetch_rss_feed_content')
    async def test_get_articles_pagination(self, mock_fetch):
        """Test article pagination functionality."""
        # Create RSS with multiple items
        rss_content = '''<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>''' + ''.join([
                    f'''<item>
                        <title>Article {i}</title>
                        <description>Description {i}</description>
                        <author>Author {i}</author>
                        <pubDate>Wed, 0{i} Aug 2025 14:41:57 +0000</pubDate>
                        <link>https://example.com/article{i}</link>
                    </item>''' for i in range(1, 11)
                ]) + '''
            </channel>
        </rss>'''
        
        mock_fetch.return_value = rss_content
        
        # Test pagination
        articles, total = await self.rss_service.get_articles(
            "https://example.com/feed", 
            skip=2, 
            limit=3
        )
        
        self.assertEqual(total, 10)
        self.assertEqual(len(articles), 3)
        self.assertEqual(articles[0].title, "Article 3")  # Skip 2, start from 3rd


class TestUtilityMethods(unittest.TestCase):
    """Test cases for new utility methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.rss_service = RSSService()

    @patch('requests.get')
    def test_fetch_rss_feed_content_valid(self, mock_get):
        """Test fetching valid RSS feed content."""
        valid_rss = '''<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item><title>Test Item</title></item>
            </channel>
        </rss>'''
        
        mock_get.return_value = MockResponse(valid_rss, 200)
        
        result = self.rss_service.fetch_rss_feed_content("https://example.com/feed")
        
        self.assertEqual(result, valid_rss)
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_fetch_rss_feed_content_invalid(self, mock_get):
        """Test fetching invalid RSS feed content."""
        invalid_content = "<html><body>Not RSS</body></html>"
        
        mock_get.return_value = MockResponse(invalid_content, 200)
        
        with self.assertRaises(ValueError):
            self.rss_service.fetch_rss_feed_content("https://example.com/feed")

    @patch('requests.get')
    def test_fetch_rss_feed_content_request_error(self, mock_get):
        """Test fetching RSS feed content with request error."""
        mock_get.side_effect = requests.RequestException("Network error")
        
        with self.assertRaises(requests.RequestException):
            self.rss_service.fetch_rss_feed_content("https://example.com/feed")

    async def test_fetch_articles_from_feeds_multiple_feeds(self):
        """Test fetching articles from multiple feeds."""
        feed_urls = [
            "https://example.com/feed1",
            "https://example.com/feed2"
        ]
        
        # Mock get_articles method
        with patch.object(self.rss_service, 'get_articles') as mock_get_articles:
            # Create mock articles
            from models import Article
            from uuid import uuid4
            
            mock_articles = [
                Article(
                    id=uuid4(),
                    title=f"Article {i}",
                    subtitle=f"Subtitle {i}",
                    author=f"Author {i}",
                    content_url=f"https://example.com/article{i}",
                    date_published=datetime.now(timezone.utc)
                ) for i in range(1, 4)
            ]
            
            mock_get_articles.return_value = (mock_articles, len(mock_articles))
            
            result = await self.rss_service.fetch_articles_from_feeds(feed_urls)
            
            # Should be called twice (once per feed)
            self.assertEqual(mock_get_articles.call_count, 2)
            self.assertEqual(len(result), 6)  # 3 articles per feed

    async def test_fetch_articles_from_feeds_with_date_filter(self):
        """Test fetching articles with date filtering."""
        feed_urls = ["https://example.com/feed"]
        start_date = datetime.now() - timezone.utc
        
        with patch.object(self.rss_service, 'get_articles') as mock_get_articles:
            with patch.object(self.rss_service, 'filter_articles_by_date') as mock_filter:
                mock_get_articles.return_value = ([], 0)
                mock_filter.return_value = []
                
                await self.rss_service.fetch_articles_from_feeds(
                    feed_urls, 
                    start_date=start_date
                )
                
                mock_filter.assert_called_once()

    async def test_fetch_articles_from_feeds_error_handling(self):
        """Test error handling in fetch_articles_from_feeds."""
        feed_urls = [
            "https://example.com/good-feed",
            "https://example.com/bad-feed"
        ]
        
        with patch.object(self.rss_service, 'get_articles') as mock_get_articles:
            # First call succeeds, second fails
            mock_get_articles.side_effect = [
                ([], 0),  # Success
                Exception("Feed error")  # Failure
            ]
            
            result = await self.rss_service.fetch_articles_from_feeds(
                feed_urls, 
                verbose=True
            )
            
            # Should continue processing despite one failure
            self.assertEqual(len(result), 0)
            self.assertEqual(mock_get_articles.call_count, 2)


class TestIssueArticleFetching(unittest.TestCase):
    """Test cases for enhanced issue article fetching."""

    def setUp(self):
        """Set up test fixtures."""
        self.rss_service = RSSService()
        
        # Mock database service
        self.mock_db = MagicMock()
        self.rss_service.db = self.mock_db

    async def test_fetch_recent_articles_for_issue_success(self):
        """Test successful fetching of recent articles for an issue."""
        issue_id = "test-issue-123"
        
        # Mock database responses
        self.mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {'id': issue_id, 'title': 'Test Issue', 'format': 'newspaper'}
        ]
        
        # Mock publications for issue
        publications_data = [
            {
                'publications': {
                    'id': 'pub-1',
                    'title': 'Test Publication',
                    'rss_feed_url': 'https://example.com/feed1',
                    'publisher': 'Test Publisher'
                }
            }
        ]
        
        self.mock_db.client.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{'id': issue_id, 'title': 'Test Issue', 'format': 'newspaper'}]),
            MagicMock(data=publications_data)
        ]
        
        # Mock get_articles method
        with patch.object(self.rss_service, 'get_articles') as mock_get_articles:
            from models import Article
            from uuid import uuid4
            
            mock_article = Article(
                id=uuid4(),
                title="Recent Article",
                subtitle="Article subtitle",
                author="Test Author",
                content_url="https://example.com/article",
                date_published=datetime.now(timezone.utc)
            )
            
            mock_get_articles.return_value = ([mock_article], 1)
            
            result = await self.rss_service.fetch_recent_articles_for_issue(issue_id)
            
            self.assertIn('issue', result)
            self.assertIn('publications', result)
            self.assertIn('articles_by_publication', result)
            self.assertIn('total_articles', result)
            self.assertEqual(result['total_articles'], 1)

    async def test_fetch_recent_articles_for_issue_not_found(self):
        """Test fetching articles for non-existent issue."""
        issue_id = "non-existent-issue"
        
        # Mock database to return no issue
        self.mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        
        with self.assertRaises(ValueError):
            await self.rss_service.fetch_recent_articles_for_issue(issue_id)

    async def test_fetch_recent_articles_for_issue_no_publications(self):
        """Test fetching articles for issue with no publications."""
        issue_id = "test-issue-123"
        
        # Mock database responses
        self.mock_db.client.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{'id': issue_id, 'title': 'Test Issue', 'format': 'newspaper'}]),
            MagicMock(data=[])  # No publications
        ]
        
        result = await self.rss_service.fetch_recent_articles_for_issue(issue_id)
        
        self.assertEqual(result['total_articles'], 0)
        self.assertEqual(len(result['publications']), 0)

    async def test_fetch_recent_articles_for_issue_custom_parameters(self):
        """Test fetching articles with custom parameters."""
        issue_id = "test-issue-123"
        
        # Mock database responses
        self.mock_db.client.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{'id': issue_id, 'title': 'Test Issue', 'format': 'newspaper'}]),
            MagicMock(data=[{
                'publications': {
                    'id': 'pub-1',
                    'title': 'Test Publication',
                    'rss_feed_url': 'https://example.com/feed1',
                    'publisher': 'Test Publisher'
                }
            }])
        ]
        
        with patch.object(self.rss_service, 'get_articles') as mock_get_articles:
            mock_get_articles.return_value = ([], 0)
            
            await self.rss_service.fetch_recent_articles_for_issue(
                issue_id,
                days_back=14,
                max_articles_per_publication=10
            )
            
            # Verify get_articles was called with correct limit
            mock_get_articles.assert_called_with(
                'https://example.com/feed1',
                skip=0,
                limit=20  # max_articles_per_publication * 2
            )


if __name__ == '__main__':
    unittest.main()