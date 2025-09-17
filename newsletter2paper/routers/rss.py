from fastapi import APIRouter, HTTPException
from services.rss_service import RSSService

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