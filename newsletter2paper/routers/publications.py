from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel

from services.database_service import DatabaseService

router = APIRouter(prefix="/publications", tags=["publications"])

class CreatePublicationRequest(BaseModel):
    title: str
    url: str
    rss_feed_url: str
    publisher: str

# Dependency to get database service
def get_db_service():
    return DatabaseService()

@router.get("/", response_model=dict)
async def get_publications(
    search: Optional[str] = None,
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Get all publications, optionally filtered by search term.
    """
    try:
        query = db_service.client.table('publications').select('*')
        
        if search:
            # Search in title or publisher
            query = query.or_(f'title.ilike.%{search}%,publisher.ilike.%{search}%')
        
        result = query.execute()
        
        return {
            "success": True,
            "publications": result.data or [],
            "count": len(result.data) if result.data else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get publications: {str(e)}")

@router.post("/", response_model=dict)
async def create_publication(
    request: CreatePublicationRequest,
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Create a new publication.
    """
    try:
        # Check if publication already exists by URL
        existing = db_service.client.table('publications')\
            .select('id')\
            .eq('url', request.url)\
            .execute()
        
        if existing.data:
            raise HTTPException(status_code=400, detail="Publication with this URL already exists")
        
        publication_data = {
            'title': request.title,
            'url': request.url,
            'rss_feed_url': request.rss_feed_url,
            'publisher': request.publisher
        }
        
        result = db_service.client.table('publications').insert(publication_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create publication")
            
        return {
            "success": True,
            "publication": result.data[0],
            "message": "Publication created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create publication: {str(e)}")

@router.get("/{publication_id}", response_model=dict)
async def get_publication(
    publication_id: UUID,
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Get a specific publication by ID.
    """
    try:
        result = db_service.client.table('publications')\
            .select('*')\
            .eq('id', str(publication_id))\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Publication not found")
            
        return {
            "success": True,
            "publication": result.data[0]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get publication: {str(e)}")

@router.post("/find-or-create", response_model=dict)
async def find_or_create_publication(
    request: CreatePublicationRequest,
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Find an existing publication by URL or create a new one if it doesn't exist.
    This is useful for the frontend when adding publications from search results.
    """
    try:
        # First try to find by URL
        existing = db_service.client.table('publications')\
            .select('*')\
            .eq('url', request.url)\
            .execute()
        
        if existing.data:
            return {
                "success": True,
                "publication": existing.data[0],
                "created": False,
                "message": "Found existing publication"
            }
        
        # If not found, create new publication
        publication_data = {
            'title': request.title,
            'url': request.url,
            'rss_feed_url': request.rss_feed_url,
            'publisher': request.publisher
        }
        
        result = db_service.client.table('publications').insert(publication_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create publication")
            
        return {
            "success": True,
            "publication": result.data[0],
            "created": True,
            "message": "Created new publication"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find or create publication: {str(e)}")