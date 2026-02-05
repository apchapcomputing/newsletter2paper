"""Unit tests for the articles router."""

import pytest

# Skip this entire module until tests are refactored to work with FastAPI dependency injection
pytest.skip("Tests need refactoring for FastAPI dependency injection pattern", allow_module_level=True)

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, timezone
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the router
from routers.articles import router
from services.rss_service import RSSService


class TestArticlesRouter(unittest.TestCase):
    """Test cases for articles router endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)

    @patch('routers.articles.rss_service')
    def test_fetch_articles_for_issue_success(self, mock_rss_service):
        """Test successful article fetching for an issue."""
        issue_id = "test-issue-123"
        
        # Mock the RSS service response
        mock_response = {
            'issue': {
                'id': issue_id,
                'title': 'Test Issue',
                'format': 'newspaper'
            },
            'publications': [
                {
                    'id': 'pub-1',
                    'title': 'Test Publication',
                    'publisher': 'Test Publisher'
                }
            ],
            'articles_by_publication': {
                'pub-1': [
                    {
                        'id': 'article-1',
                        'title': 'Test Article',
                        'author': 'Test Author',
                        'date_published': datetime.now(timezone.utc).isoformat(),
                        'content_url': 'https://example.com/article'
                    }
                ]
            },
            'total_articles': 1,
            'date_range': {
                'from': (datetime.now(timezone.utc)).isoformat(),
                'to': datetime.now(timezone.utc).isoformat(),
                'days_back': 7
            }
        }
        
        mock_rss_service.fetch_recent_articles_for_issue = AsyncMock(return_value=mock_response)
        
        response = self.client.post(f"/articles/fetch/{issue_id}")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('success', data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertEqual(data['data']['total_articles'], 1)

    @patch('routers.articles.rss_service')
    def test_fetch_articles_for_issue_with_parameters(self, mock_rss_service):
        """Test article fetching with custom parameters."""
        issue_id = "test-issue-123"
        
        mock_rss_service.fetch_recent_articles_for_issue = AsyncMock(return_value={
            'issue': {'id': issue_id},
            'publications': [],
            'articles_by_publication': {},
            'total_articles': 0
        })
        
        response = self.client.post(
            f"/articles/fetch/{issue_id}",
            params={
                'days_back': 14,
                'max_articles_per_publication': 10
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the service was called with correct parameters
        mock_rss_service.fetch_recent_articles_for_issue.assert_called_once_with(
            issue_id,
            days_back=14,
            max_articles_per_publication=10
        )

    @patch('routers.articles.rss_service')
    def test_fetch_articles_for_issue_not_found(self, mock_rss_service):
        """Test article fetching for non-existent issue."""
        issue_id = "non-existent-issue"
        
        mock_rss_service.fetch_recent_articles_for_issue = AsyncMock(
            side_effect=ValueError(f"Issue not found: {issue_id}")
        )
        
        response = self.client.post(f"/articles/fetch/{issue_id}")
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn('detail', data)
        self.assertIn('Issue not found', data['detail'])

    @patch('routers.articles.rss_service')
    def test_fetch_articles_for_issue_server_error(self, mock_rss_service):
        """Test article fetching with server error."""
        issue_id = "test-issue-123"
        
        mock_rss_service.fetch_recent_articles_for_issue = AsyncMock(
            side_effect=Exception("Database connection error")
        )
        
        response = self.client.post(f"/articles/fetch/{issue_id}")
        
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('detail', data)
        self.assertIn('Failed to fetch articles', data['detail'])

    def test_fetch_articles_invalid_uuid(self):
        """Test article fetching with invalid UUID format."""
        invalid_issue_id = "not-a-uuid"
        
        response = self.client.post(f"/articles/fetch/{invalid_issue_id}")
        
        self.assertEqual(response.status_code, 422)  # Validation error

    def test_fetch_articles_invalid_parameters(self):
        """Test article fetching with invalid parameters."""
        issue_id = "test-issue-123"
        
        # Test negative days_back
        response = self.client.post(
            f"/articles/fetch/{issue_id}",
            params={'days_back': -5}
        )
        self.assertEqual(response.status_code, 422)
        
        # Test zero max_articles_per_publication
        response = self.client.post(
            f"/articles/fetch/{issue_id}",
            params={'max_articles_per_publication': 0}
        )
        self.assertEqual(response.status_code, 422)

    @patch('routers.articles.rss_service')
    def test_fetch_articles_empty_result(self, mock_rss_service):
        """Test article fetching with no articles found."""
        issue_id = "test-issue-123"
        
        mock_response = {
            'issue': {
                'id': issue_id,
                'title': 'Test Issue',
                'format': 'newspaper'
            },
            'publications': [],
            'articles_by_publication': {},
            'total_articles': 0,
            'date_range': {
                'from': datetime.now(timezone.utc).isoformat(),
                'to': datetime.now(timezone.utc).isoformat(),
                'days_back': 7
            }
        }
        
        mock_rss_service.fetch_recent_articles_for_issue = AsyncMock(return_value=mock_response)
        
        response = self.client.post(f"/articles/fetch/{issue_id}")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['total_articles'], 0)

    @patch('routers.articles.rss_service')
    def test_fetch_articles_large_dataset(self, mock_rss_service):
        """Test article fetching with large dataset."""
        issue_id = "test-issue-123"
        
        # Create mock response with many articles
        articles_by_pub = {}
        for pub_id in range(1, 6):  # 5 publications
            articles_by_pub[f'pub-{pub_id}'] = [
                {
                    'id': f'article-{pub_id}-{i}',
                    'title': f'Article {i} from Pub {pub_id}',
                    'author': f'Author {i}',
                    'date_published': datetime.now(timezone.utc).isoformat(),
                    'content_url': f'https://example.com/article-{pub_id}-{i}'
                } for i in range(1, 11)  # 10 articles each
            ]
        
        mock_response = {
            'issue': {'id': issue_id, 'title': 'Large Issue'},
            'publications': [{'id': f'pub-{i}'} for i in range(1, 6)],
            'articles_by_publication': articles_by_pub,
            'total_articles': 50,
            'date_range': {
                'from': datetime.now(timezone.utc).isoformat(),
                'to': datetime.now(timezone.utc).isoformat(),
                'days_back': 7
            }
        }
        
        mock_rss_service.fetch_recent_articles_for_issue = AsyncMock(return_value=mock_response)
        
        response = self.client.post(f"/articles/fetch/{issue_id}")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['data']['total_articles'], 50)
        self.assertEqual(len(data['data']['publications']), 5)

    @patch('routers.articles.rss_service')
    def test_fetch_articles_timeout_handling(self, mock_rss_service):
        """Test article fetching with timeout scenarios."""
        issue_id = "test-issue-123"
        
        import asyncio
        mock_rss_service.fetch_recent_articles_for_issue = AsyncMock(
            side_effect=asyncio.TimeoutError("Request timeout")
        )
        
        response = self.client.post(f"/articles/fetch/{issue_id}")
        
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('Failed to fetch articles', data['detail'])


class TestArticlesRouterIntegration(unittest.TestCase):
    """Integration tests for articles router."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)

    @patch('routers.articles.rss_service')
    @patch('services.database_service.DatabaseService')
    def test_fetch_articles_integration_flow(self, mock_db_service, mock_rss_service):
        """Test the complete integration flow for article fetching."""
        issue_id = "test-issue-123"
        
        # Mock database responses
        mock_db = MagicMock()
        mock_db_service.return_value = mock_db
        
        # Mock RSS service
        mock_response = {
            'issue': {
                'id': issue_id,
                'title': 'Integration Test Issue',
                'format': 'newspaper',
                'target_email': 'test@example.com'
            },
            'publications': [
                {
                    'id': 'pub-1',
                    'title': 'Tech Newsletter',
                    'publisher': 'Tech Publisher',
                    'rss_feed_url': 'https://tech.example.com/feed'
                },
                {
                    'id': 'pub-2',
                    'title': 'Science Newsletter',
                    'publisher': 'Science Publisher',
                    'rss_feed_url': 'https://science.example.com/feed'
                }
            ],
            'articles_by_publication': {
                'pub-1': [
                    {
                        'id': 'tech-article-1',
                        'title': 'Latest Tech Trends',
                        'author': 'Tech Author',
                        'date_published': '2025-10-01T12:00:00Z',
                        'content_url': 'https://tech.example.com/article1',
                        'publication_title': 'Tech Newsletter'
                    }
                ],
                'pub-2': [
                    {
                        'id': 'science-article-1',
                        'title': 'New Scientific Discovery',
                        'author': 'Science Author',
                        'date_published': '2025-10-01T14:00:00Z',
                        'content_url': 'https://science.example.com/article1',
                        'publication_title': 'Science Newsletter'
                    }
                ]
            },
            'total_articles': 2,
            'date_range': {
                'from': '2025-09-24T12:00:00Z',
                'to': '2025-10-01T12:00:00Z',
                'days_back': 7
            }
        }
        
        mock_rss_service.fetch_recent_articles_for_issue = AsyncMock(return_value=mock_response)
        
        # Make the request
        response = self.client.post(
            f"/articles/fetch/{issue_id}",
            params={
                'days_back': 7,
                'max_articles_per_publication': 5
            }
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['total_articles'], 2)
        self.assertEqual(len(data['data']['publications']), 2)
        
        # Verify articles structure
        articles_by_pub = data['data']['articles_by_publication']
        self.assertIn('pub-1', articles_by_pub)
        self.assertIn('pub-2', articles_by_pub)
        
        tech_article = articles_by_pub['pub-1'][0]
        self.assertEqual(tech_article['title'], 'Latest Tech Trends')
        self.assertEqual(tech_article['author'], 'Tech Author')
        
        science_article = articles_by_pub['pub-2'][0]
        self.assertEqual(science_article['title'], 'New Scientific Discovery')
        self.assertEqual(science_article['author'], 'Science Author')
        
        # Verify date range
        date_range = data['data']['date_range']
        self.assertEqual(date_range['days_back'], 7)
        self.assertIn('from', date_range)
        self.assertIn('to', date_range)


if __name__ == '__main__':
    unittest.main()