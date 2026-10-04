"""
One-off article conversion endpoint.
Converts a single article URL to a PDF without requiring a pre-configured publication or issue.
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from services.go_pdf_service import GoPDFService
from services.platform_service import PlatformService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oneoff", tags=["oneoff"])


class OneOffArticleRequest(BaseModel):
    url: str
    layout_type: str = "essay"
    platform: Optional[str] = None
    remove_images: bool = False


@router.post("/article", response_model=dict)
async def convert_article(request: OneOffArticleRequest):
    """
    Convert a single article URL to a PDF.

    Accepts any article URL. Platform is auto-detected from the URL and page content.
    Returns a signed download URL valid for 30 days.
    """
    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="url must start with http:// or https://")

    if request.layout_type not in ("essay", "newspaper"):
        raise HTTPException(status_code=422, detail="layout_type must be 'essay' or 'newspaper'")

    platform = request.platform
    if not platform:
        platform = PlatformService().detect(request.url, fetch_html_on_miss=True)

    issue_id = str(uuid.uuid4())
    issue_info = {
        "id": issue_id,
        "title": "One-Off Article",
        "description": "",
    }

    articles = [{
        "title": "",
        "content_url": request.url,
        "platform": platform,
        "remove_images": request.remove_images,
    }]

    try:
        pdf_service = GoPDFService()
        result = await pdf_service.generate_pdf_from_issue(
            issue_id=issue_id,
            articles=articles,
            issue_info=issue_info,
            layout_type=request.layout_type,
            remove_images=request.remove_images,
        )
    except Exception as e:
        logger.error(f"One-off PDF generation failed for {request.url}: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error") or "PDF generation failed"
        )

    return {
        "success": True,
        "pdf_url": result["pdf_url"],
        "layout_type": request.layout_type,
        "platform_detected": platform,
        "url": request.url,
    }
