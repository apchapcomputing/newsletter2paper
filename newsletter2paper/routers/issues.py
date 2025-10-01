from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from services.database_service import DatabaseService
from models.issue import Issue
from models.issue_publication import IssuePublication

router = APIRouter(prefix="/issues", tags=["issues"])

# Pydantic models for requests
class CreateIssueRequest(BaseModel):
    title: str = "Your Newspaper"
    format: str  # "newspaper" or "essay"
    frequency: str = "weekly"  # "daily", "weekly", "monthly"
    target_email: Optional[str] = None

class UpdateIssueRequest(BaseModel):
    title: Optional[str] = None
    format: Optional[str] = None
    frequency: Optional[str] = None
    target_email: Optional[str] = None

class AddPublicationsRequest(BaseModel):
    publication_ids: List[UUID]

# Dependency to get database service
def get_db_service():
    return DatabaseService()

@router.post("/", response_model=dict)
async def create_issue(
    request: CreateIssueRequest,
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Create a new issue with the specified title and format.
    """
    try:
        # Create the issue in the database
        issue_data = {
            'title': request.title,
            'format': request.format,
            'frequency': request.frequency,
            'target_email': request.target_email,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = db_service.client.table('issues').insert(issue_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create issue")
            
        return {
            "success": True,
            "issue": result.data[0],
            "message": "Issue created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create issue: {str(e)}")

@router.put("/{issue_id}", response_model=dict)
async def update_issue(
    issue_id: UUID,
    request: UpdateIssueRequest,
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Update an existing issue with new title and/or format.
    """
    try:
        # Prepare update data (only include non-None values)
        update_data = {
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        if request.title is not None:
            update_data['title'] = request.title
        if request.format is not None:
            update_data['format'] = request.format
        if request.frequency is not None:
            update_data['frequency'] = request.frequency
        if request.target_email is not None:
            update_data['target_email'] = request.target_email
        
        # Update the issue in the database
        result = db_service.client.table('issues')\
            .update(update_data)\
            .eq('id', str(issue_id))\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Issue not found")
            
        return {
            "success": True,
            "issue": result.data[0],
            "message": "Issue updated successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update issue: {str(e)}")

@router.get("/{issue_id}", response_model=dict)
async def get_issue(
    issue_id: UUID,
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Get a specific issue by ID.
    """
    try:
        result = db_service.client.table('issues')\
            .select('*')\
            .eq('id', str(issue_id))\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Issue not found")
            
        return {
            "success": True,
            "issue": result.data[0]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get issue: {str(e)}")

@router.post("/{issue_id}/publications", response_model=dict)
async def add_publications_to_issue(
    issue_id: UUID,
    request: AddPublicationsRequest,
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Add selected publications to an issue.
    """
    try:
        # First verify the issue exists
        issue_result = db_service.client.table('issues')\
            .select('id')\
            .eq('id', str(issue_id))\
            .execute()
        
        if not issue_result.data:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        # Remove existing publications for this issue
        db_service.client.table('issue_publications')\
            .delete()\
            .eq('issue_id', str(issue_id))\
            .execute()
        
        # Add new publications
        if request.publication_ids:
            issue_publications_data = []
            for pub_id in request.publication_ids:
                issue_publications_data.append({
                    'issue_id': str(issue_id),
                    'publication_id': str(pub_id),
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })
            
            result = db_service.client.table('issue_publications')\
                .insert(issue_publications_data)\
                .execute()
            
            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to add publications to issue")
        
        return {
            "success": True,
            "message": f"Added {len(request.publication_ids)} publications to issue",
            "issue_id": str(issue_id),
            "publication_count": len(request.publication_ids)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add publications to issue: {str(e)}")

@router.get("/{issue_id}/publications", response_model=dict)
async def get_issue_publications(
    issue_id: UUID,
    db_service: DatabaseService = Depends(get_db_service)
):
    """
    Get all publications associated with an issue.
    """
    try:
        # Get publications for this issue with a join
        result = db_service.client.table('issue_publications')\
            .select('*, publications(*)')\
            .eq('issue_id', str(issue_id))\
            .execute()
        
        publications = []
        if result.data:
            publications = [item['publications'] for item in result.data if item['publications']]
        
        return {
            "success": True,
            "issue_id": str(issue_id),
            "publications": publications,
            "count": len(publications)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get issue publications: {str(e)}")