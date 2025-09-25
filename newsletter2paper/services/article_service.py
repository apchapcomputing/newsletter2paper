"""
Service for managing Article operations including database storage and retrieval.
"""

from typing import List, Optional
from datetime import datetime
import logging
from models.article import Article
from services.database_service import DatabaseService


class ArticleService:
    def __init__(self):
        """Initialize the article service with database connection."""
        self.db = DatabaseService()

    async def store_articles(self, articles: List[Article]) -> List[Article]:
        """
        Store multiple articles in the database.
        
        Args:
            articles: List of Article objects to store
            
        Returns:
            List[Article]: List of stored articles with updated IDs
            
        Raises:
            Exception: If database operation fails
        """
        try:
            stored_articles = []
            for article in articles:
                stored_article = await self.store_article(article)
                stored_articles.append(stored_article)
            return stored_articles
        
        except Exception as e:
            logging.error(f"Failed to store articles batch: {str(e)}")
            raise

    async def store_article(self, article: Article) -> Article:
        """
        Store a single article in the database.
        
        Args:
            article: Article object to store
            
        Returns:
            Article: Stored article with updated ID
            
        Raises:
            Exception: If database operation fails
        """
        try:
            # Convert article to dict for storage
            article_data = {
                'id': str(article.id),
                'title': article.title,
                'subtitle': article.subtitle,
                'date_published': article.date_published.isoformat(),
                'author': article.author,
                'publication_id': str(article.publication_id) if article.publication_id else None,
                'content_url': article.content_url,
                'storage_url': article.storage_url,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Store in database
            result = await self.db.store_article(
                title=article.title,
                subtitle=article.subtitle,
                date_published=article.date_published,
                author=article.author,
                publication_id=article.publication_id,
                content_url=article.content_url,
                storage_url=article.storage_url
            )
            
            # Update article with stored data
            article.id = result['id']
            article.created_at = datetime.fromisoformat(result['created_at'])
            article.updated_at = datetime.fromisoformat(result['updated_at'])
            
            return article
            
        except Exception as e:
            logging.error(f"Failed to store article '{article.title}': {str(e)}")
            raise

    async def get_article_by_url(self, content_url: str) -> Optional[Article]:
        """
        Retrieve an article by its content URL to check for duplicates.
        
        Args:
            content_url: URL of the article content
            
        Returns:
            Optional[Article]: Article if found, None otherwise
        """
        try:
            result = await self.db.query_articles_table(
                query="content_url", value=content_url, single=True
            )
            if result:
                return Article.model_validate(result)
            return None
            
        except Exception as e:
            logging.error(f"Failed to query article by URL '{content_url}': {str(e)}")
            raise