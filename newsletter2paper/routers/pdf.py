"""
PDF Router Module
Handles PDF generation endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from typing import Optional
import logging
from pathlib import Path

from services.pdf_service import PDFService

router = APIRouter(prefix="/pdf", tags=["pdf"])
pdf_service = PDFService()


@router.post("/generate/{issue_id}")
async def generate_pdf_for_issue(
    issue_id: str,
    days_back: int = Query(7, description="Number of days to look back for articles"),
    max_articles_per_publication: int = Query(5, description="Maximum articles per publication"),
    layout_type: str = Query("newspaper", description="Layout type: 'newspaper' or 'essay'"),
    output_filename: Optional[str] = Query(None, description="Custom output filename"),
    keep_html: bool = Query(False, description="Whether to keep intermediate HTML file"),
    verbose: bool = Query(False, description="Enable verbose logging")
):
    """
    Generate a PDF from an issue's articles.
    
    Args:
        issue_id: UUID of the issue
        days_back: Number of days to look back for articles
        max_articles_per_publication: Maximum articles per publication
        layout_type: Layout type ('newspaper' or 'essay')
        output_filename: Custom output filename (without extension)
        keep_html: Whether to keep the intermediate HTML file
        verbose: Enable verbose output
        
    Returns:
        dict: Result with success status, file paths, and metadata
    """
    try:
        if verbose:
            logging.info(f"Generating PDF for issue {issue_id} with layout {layout_type}")
        
        result = await pdf_service.generate_pdf_from_issue(
            issue_id=issue_id,
            days_back=days_back,
            max_articles_per_publication=max_articles_per_publication,
            output_filename=output_filename,
            keep_html=keep_html,
            verbose=verbose
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'PDF generation failed'))
        
        return {
            "success": True,
            "message": "PDF generated successfully",
            "pdf_url": result['pdf_url'],
            "html_path": result.get('html_path'),
            "issue_info": result['issue_info'],
            "articles_count": result['articles_count']
        }
        
    except Exception as e:
        logging.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.get("/download/{issue_id}")
async def download_pdf(
    issue_id: str,
    days_back: int = Query(7, description="Number of days to look back for articles"),
    max_articles_per_publication: int = Query(5, description="Maximum articles per publication"),
    layout_type: str = Query("newspaper", description="Layout type: 'newspaper' or 'essay'"),
    output_filename: Optional[str] = Query(None, description="Custom output filename")
):
    """
    Generate and download a PDF for an issue by redirecting to the Supabase storage URL.
    
    Args:
        issue_id: UUID of the issue
        days_back: Number of days to look back for articles
        max_articles_per_publication: Maximum articles per publication
        layout_type: Layout type ('newspaper' or 'essay')
        output_filename: Custom output filename (without extension)
        
    Returns:
        RedirectResponse: Redirect to the PDF URL in Supabase storage
    """
    try:
        result = await pdf_service.generate_pdf_from_issue(
            issue_id=issue_id,
            days_back=days_back,
            max_articles_per_publication=max_articles_per_publication,
            output_filename=output_filename,
            keep_html=False,
            verbose=False
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'PDF generation failed'))
        
        pdf_url = result['pdf_url']
        if not pdf_url:
            raise HTTPException(status_code=404, detail="Generated PDF URL not found")
        
        # Redirect to the Supabase storage URL for direct download
        return RedirectResponse(url=pdf_url, status_code=302)
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"PDF download failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF download failed: {str(e)}")


@router.get("/status/{issue_id}")
async def get_pdf_status(issue_id: str):
    """
    Check PDF generation status for an issue.
    
    Args:
        issue_id: UUID of the issue
        
    Returns:
        dict: Status information about PDF generation capabilities
    """
    try:
        # Since PDFs are now generated on-demand and stored in Supabase storage,
        # this endpoint provides information about the generation capability
        return {
            "issue_id": issue_id,
            "storage_type": "supabase",
            "generation_available": True,
            "message": "PDFs are generated on-demand and stored in cloud storage",
            "endpoints": {
                "generate": f"/pdf/generate/{issue_id}",
                "download": f"/pdf/download/{issue_id}"
            }
        }
        
    except Exception as e:
        logging.error(f"PDF status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.get("/test-storage")
async def test_storage_access():
    """
    Test Supabase storage access for debugging.
    
    Returns:
        dict: Storage access test results
    """
    try:
        # Check bucket access
        bucket_info = pdf_service.storage_service.check_bucket_access()
        
        return {
            "storage_test": bucket_info,
            "supabase_configured": True,
            "message": "Storage access test completed"
        }
        
    except Exception as e:
        logging.error(f"Storage test failed: {e}")
        return {
            "storage_test": {
                "success": False,
                "error": str(e)
            },
            "supabase_configured": False,
            "message": f"Storage test failed: {str(e)}"
        }


@router.delete("/cleanup")
async def cleanup_old_files(days_old: int = Query(7, description="Delete local files older than this many days")):
    """
    Clean up old local files (HTML and any remaining PDFs).
    Note: PDFs are now stored in Supabase storage and need to be managed separately.
    
    Args:
        days_old: Delete local files older than this many days
        
    Returns:
        dict: Cleanup results
    """
    try:
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        pdf_dir = pdf_service.output_dir
        
        deleted_files = []
        total_size_freed = 0
        
        # Clean up any remaining local PDF files (legacy)
        for pdf_file in pdf_dir.glob("*.pdf"):
            file_mtime = datetime.fromtimestamp(pdf_file.stat().st_mtime)
            if file_mtime < cutoff_date:
                file_size = pdf_file.stat().st_size
                pdf_file.unlink()
                deleted_files.append(pdf_file.name)
                total_size_freed += file_size
        
        # Clean up HTML files
        for html_file in pdf_dir.glob("*.html"):
            file_mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
            if file_mtime < cutoff_date:
                file_size = html_file.stat().st_size
                html_file.unlink()
                deleted_files.append(html_file.name)
                total_size_freed += file_size
        
        return {
            "success": True,
            "files_deleted": len(deleted_files),
            "deleted_files": deleted_files,
            "total_size_freed_bytes": total_size_freed,
            "cutoff_date": cutoff_date.isoformat(),
            "note": "PDFs are now stored in Supabase storage. Cloud storage cleanup should be managed through Supabase console or API."
        }
        
    except Exception as e:
        logging.error(f"File cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")