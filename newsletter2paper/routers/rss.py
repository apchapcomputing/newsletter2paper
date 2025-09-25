from fastapi import APIRouter, HTTPException, Query
from services.rss_service import RSSService
from models.api import ArticleResponse, PaginatedArticlesResponse
from typing import List

router = APIRouter(prefix="/rss", tags=["RSS"])
rss_service = RSSService()

@router.get("/url")
async def get_rss_feed_url(webpage_url: str) -> dict:
    """
    Discover RSS feed URL from a given webpage URL.
    
    Args:
        webpage_url (str): URL of the webpage to check for RSS feeds
        
    Returns:
        dict: Contains the discovered RSS feed URL or error message
    """
    try:
        feed_url = rss_service.get_feed_url(webpage_url)
        if feed_url:
            return {"feed_url": feed_url}
        else:
            raise HTTPException(status_code=404, detail="No RSS feed found for the given URL")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/articles", response_model=PaginatedArticlesResponse, summary="Get articles from RSS feed")
async def get_feed_articles(
    feed_url: str = Query(
        ...,
        title="Feed URL",
        description="URL of the RSS feed to fetch articles from",
        example="https://kyla.substack.com/feed"
    ),
    skip: int = Query(
        default=0,
        title="Skip",
        description="Number of articles to skip for pagination",
        example=0,
        ge=0
    ),
    limit: int = Query(
        default=5,
        title="Limit",
        description="Maximum number of articles to return (1-20)",
        example=5,
        ge=1,
        le=20
    )
) -> PaginatedArticlesResponse:
    """
    Fetch and parse articles from an RSS feed with pagination.
    
    Args:
        feed_url: URL of the RSS feed to fetch articles from
        skip: Number of articles to skip (for pagination)
        limit: Maximum number of articles to return (1-100)
        
    Returns:
        PaginatedArticlesResponse: Paginated list of articles with metadata
        
    Raises:
        HTTPException: If feed cannot be fetched or parsed
    """
    try:
        articles, total = rss_service.get_articles(feed_url, skip, limit)
        
        return PaginatedArticlesResponse(
            items=articles,
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + len(articles) < total)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch articles from feed: {str(e)}"
        )