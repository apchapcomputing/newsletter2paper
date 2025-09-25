"""
Service for managing Supabase database operations.
"""

import os
from datetime import datetime, timezone
import uuid
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

class DatabaseService:
    def __init__(self):
        """Initialize Supabase client using environment variables."""
        self.client: Client = create_client(
            os.environ.get('SUPABASE_URL', ''),
            os.environ.get('SUPABASE_KEY', '')
        )

    async def store_article(self, 
                          title: str, 
                          subtitle: Optional[str], 
                          date_published: datetime, 
                          author: str, 
                          publication_id: Optional[str], 
                          content_url: str, 
                          storage_url: Optional[str] = None,
                          update_if_exists: bool = True) -> dict:
        """
        Store article information in the Supabase database.
        
        Args:
            title: Article title
            subtitle: Article subtitle or None
            date_published: Publication date
            author: Author name
            publication_id: UUID of the publication
            content_url: URL to the article content
            storage_url: Optional URL to stored content
            update_if_exists: Whether to update existing article if found by content_url
            
        Returns:
            dict: Created or updated article record
            
        Raises:
            Exception: If database operation fails
        """
        try:
            # Check if article already exists
            existing = await self.query_articles_table(query="content_url", value=content_url, single=True)
            
            now = datetime.now(timezone.utc).isoformat()
            
            if existing and update_if_exists:
                # Update existing article
                article_data = {
                    'title': title,
                    'subtitle': subtitle,
                    'date_published': date_published.isoformat(),
                    'author': author,
                    'publication_id': publication_id,
                    'content_url': content_url,
                    'storage_url': storage_url,
                    'updated_at': now
                }
                
                result = self.client.table('articles')\
                    .update(article_data)\
                    .eq('id', existing['id'])\
                    .execute()
                    
            else:
                # Create new article
                article_data = {
                    'id': str(uuid.uuid4()),
                    'title': title,
                    'subtitle': subtitle,
                    'date_published': date_published.isoformat(),
                    'author': author,
                    'publication_id': publication_id,
                    'content_url': content_url,
                    'storage_url': storage_url,
                    'created_at': now,
                    'updated_at': now
                }
                
                result = self.client.table('articles').insert(article_data).execute()
            
            if result.data:
                return result.data[0]
            else:
                raise Exception("No data returned from database operation")
                
        except Exception as e:
            raise Exception(f"Failed to store article: {str(e)}")

    async def query_articles_table(self, query: str, value: str, single: bool = False) -> Optional[dict]:
        """
        Query the articles table with a field and value.
        
        Args:
            query: Field name to query
            value: Value to match
            single: Whether to return a single result
            
        Returns:
            Optional[dict]: Matching article(s) or None
            
        Raises:
            Exception: If database operation fails
        """
        try:
            result = self.client.table('articles')\
                .select('*')\
                .eq(query, value)\
                .execute()
            
            if result.data:
                return result.data[0] if single else result.data
            return None
            
        except Exception as e:
            raise Exception(f"Failed to query articles: {str(e)}")

    async def get_publication_by_url(self, feed_url: str) -> Optional[dict]:
        """
        Get publication information by RSS feed URL.
        
        Args:
            feed_url: URL of the RSS feed
            
        Returns:
            dict: Publication record or None if not found
            
        Raises:
            Exception: If database operation fails
        """
        try:
            result = self.client.table('publications')\
                .select('*')\
                .eq('rss_feed_url', feed_url)\
                .execute()
                
            if result.data:
                return result.data[0]
            return None
                
        except Exception as e:
            raise Exception(f"Failed to fetch publication: {str(e)}")