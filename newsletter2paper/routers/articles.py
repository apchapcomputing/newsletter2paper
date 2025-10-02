from fastapi import APIRouter, HTTPException, Depends, Query
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from services.database_service import DatabaseService
from services.rss_service import RSSService

router = APIRouter(prefix="/articles", tags=["articles"])

class FetchArticlesRequest(BaseModel):
    days_back: Optional[int] = 7
    max_articles_per_publication: Optional[int] = 5

# Dependencies
def get_db_service():
    return DatabaseService()

def get_rss_service():
    return RSSService()

@router.post("/fetch/{issue_id}", response_model=dict)
async def fetch_articles_for_issue(
    issue_id: UUID,
    request: FetchArticlesRequest = FetchArticlesRequest(),
    db_service: DatabaseService = Depends(get_db_service),
    rss_service: RSSService = Depends(get_rss_service)
):
    """
    Fetch recent articles for all publications in an issue.
    
    Args:
        issue_id: UUID of the issue to fetch articles for
        request: Parameters for article fetching (days_back, max_articles_per_publication)
        
    Returns:
        Dictionary containing issue info, publications, and articles grouped by publication
    """
    try:
        result = await rss_service.fetch_recent_articles_for_issue(
            issue_id=str(issue_id),
            days_back=request.days_back,
            max_articles_per_publication=request.max_articles_per_publication
        )
        
        return {
            "success": True,
            "data": result,
            "message": f"Fetched {result['total_articles']} articles from {len(result['publications'])} publications"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch articles: {str(e)}")

@router.get("/issue/{issue_id}/summary", response_model=dict)
async def get_issue_articles_summary(
    issue_id: UUID,
    days_back: int = Query(default=7, description="Number of days to look back"),
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Get a summary of articles available for an issue without fetching full content.
    
    Args:
        issue_id: UUID of the issue
        days_back: Number of days to look back
        
    Returns:
        Summary information about available articles
    """
    try:
        # Get issue and publications
        issue_result = db_service.client.table('issues')\
            .select('*')\
            .eq('id', str(issue_id))\
            .execute()
        
        if not issue_result.data:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        publications_result = db_service.client.table('issue_publications')\
            .select('*, publications(*)')\
            .eq('issue_id', str(issue_id))\
            .execute()
        
        publications = [item['publications'] for item in publications_result.data if item['publications']]
        
        return {
            "success": True,
            "issue": issue_result.data[0],
            "publications_count": len(publications),
            "publications": [
                {
                    "id": pub["id"],
                    "title": pub["title"],
                    "publisher": pub["publisher"],
                    "rss_feed_url": pub["rss_feed_url"]
                }
                for pub in publications
            ],
            "date_range": {
                "days_back": days_back,
                "from": (datetime.now(timezone.utc) - 
                        __import__('datetime').timedelta(days=days_back)).isoformat(),
                "to": datetime.now(timezone.utc).isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get issue summary: {str(e)}")

@router.get("/health", response_model=dict)
async def health_check():
    """Health check endpoint for the articles service."""
    return {
        "status": "healthy",
        "service": "articles",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }