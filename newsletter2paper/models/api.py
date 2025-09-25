from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

class ArticleResponse(BaseModel):
    """Response model for article data from RSS feeds."""
    id: UUID
    title: str
    subtitle: Optional[str] = None
    date_published: datetime
    author: str
    publication_id: Optional[UUID] = None
    content_url: str
    storage_url: Optional[str] = None

    class Config:
        """Pydantic model configuration."""
        from_attributes = True  # Allows conversion from SQLModel/SQLAlchemy objects


class PaginatedArticlesResponse(BaseModel):
    """Response model for paginated articles from RSS feeds."""
    items: List[ArticleResponse]
    total: int
    skip: int
    limit: int
    has_more: bool