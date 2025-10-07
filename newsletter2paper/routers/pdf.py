"""
PDF Router Module
Handles PDF generation endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
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
            "pdf_path": result['pdf_path'],
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
    Generate and download a PDF for an issue.
    
    Args:
        issue_id: UUID of the issue
        days_back: Number of days to look back for articles
        max_articles_per_publication: Maximum articles per publication
        layout_type: Layout type ('newspaper' or 'essay')
        output_filename: Custom output filename (without extension)
        
    Returns:
        FileResponse: PDF file for download
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
        
        pdf_path = Path(result['pdf_path'])
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="Generated PDF file not found")
        
        # Generate download filename
        issue_title = result['issue_info'].get('title', 'Newsletter')
        safe_title = "".join(c for c in issue_title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')
        download_filename = f"{safe_title}_{layout_type}.pdf"
        
        return FileResponse(
            path=str(pdf_path),
            filename=download_filename,
            media_type='application/pdf'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"PDF download failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF download failed: {str(e)}")


@router.get("/status/{issue_id}")
async def get_pdf_status(issue_id: str):
    """
    Check if a PDF exists for an issue.
    
    Args:
        issue_id: UUID of the issue
        
    Returns:
        dict: Status information about existing PDFs
    """
    try:
        # Check for existing PDF files for this issue
        pdf_dir = pdf_service.output_dir
        pdf_files = list(pdf_dir.glob(f"*{issue_id}*.pdf"))
        
        if not pdf_files:
            return {
                "exists": False,
                "message": "No PDF found for this issue"
            }
        
        # Get the most recent PDF
        latest_pdf = max(pdf_files, key=lambda p: p.stat().st_mtime)
        
        return {
            "exists": True,
            "pdf_path": str(latest_pdf),
            "filename": latest_pdf.name,
            "size_bytes": latest_pdf.stat().st_size,
            "created_at": latest_pdf.stat().st_mtime
        }
        
    except Exception as e:
        logging.error(f"PDF status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.delete("/cleanup")
async def cleanup_old_pdfs(days_old: int = Query(7, description="Delete PDFs older than this many days")):
    """
    Clean up old PDF files.
    
    Args:
        days_old: Delete PDFs older than this many days
        
    Returns:
        dict: Cleanup results
    """
    try:
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        pdf_dir = pdf_service.output_dir
        
        deleted_files = []
        total_size_freed = 0
        
        for pdf_file in pdf_dir.glob("*.pdf"):
            file_mtime = datetime.fromtimestamp(pdf_file.stat().st_mtime)
            if file_mtime < cutoff_date:
                file_size = pdf_file.stat().st_size
                pdf_file.unlink()
                deleted_files.append(pdf_file.name)
                total_size_freed += file_size
        
        # Also clean up any orphaned HTML files
        for html_file in pdf_dir.glob("*.html"):
            file_mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
            if file_mtime < cutoff_date:
                html_file.unlink()
        
        return {
            "success": True,
            "files_deleted": len(deleted_files),
            "deleted_files": deleted_files,
            "total_size_freed_bytes": total_size_freed,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logging.error(f"PDF cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")