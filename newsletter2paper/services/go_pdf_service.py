"""
Go PDF Service Module
Wrapper for calling the Go-based PDF generation CLI from Python.
"""

import os
import json
import uuid
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.storage_service import StorageService

logger = logging.getLogger(__name__)


class GoPDFService:
    """PDF Service that calls the Go CLI for PDF generation"""
    
    def __init__(self, use_docker: bool = True, shared_dir: str = "/shared"):
        """
        Initialize Go PDF Service.
        
        Args:
            use_docker: If True, calls Go CLI via docker exec. If False, calls directly.
            shared_dir: Directory for shared files between FastAPI and Go service
        """
        self.use_docker = use_docker
        self.shared_dir = Path(shared_dir)
        self.storage_service = StorageService()
        
        # Ensure shared directory exists (for non-docker local testing)
        if not use_docker:
            self.shared_dir.mkdir(exist_ok=True, parents=True)
        
        # Configuration
        self.go_container_name = os.getenv("GO_PDF_CONTAINER", "pdf-maker")
        self.go_binary_path = "/app/makepdf"
        self.default_timeout = 120  # seconds
    
    def _generate_temp_paths(self) -> tuple[Path, Path]:
        """Generate unique temporary file paths for JSON input and PDF output."""
        unique_id = uuid.uuid4().hex[:8]
        json_path = self.shared_dir / f"articles_{unique_id}.json"
        pdf_path = self.shared_dir / f"output_{unique_id}.pdf"
        return json_path, pdf_path
    
    def _cleanup_temp_files(self, *paths: Path) -> None:
        """Clean up temporary files."""
        for path in paths:
            try:
                if path.exists():
                    path.unlink()
                    logger.debug(f"Cleaned up: {path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {path}: {e}")
    
    def _prepare_article_json(self, articles: List[Dict], issue_info: Dict, layout_type: str = "newspaper") -> Dict:
        """
        Prepare the JSON payload for the Go CLI.
        
        Args:
            articles: List of article dictionaries
            issue_info: Issue metadata dictionary
            layout_type: Layout type ("essay" or "newspaper")
            
        Returns:
            Dictionary ready for JSON serialization
        """
        article_inputs = []
        
        for article in articles:
            article_input = {
                "title": article.get("title", "Untitled"),
                "subtitle": article.get("subtitle"),
                "author": article.get("author"),
                "publication": article.get("publication_title") or article.get("publication_publisher"),
                "date_published": article.get("date_published"),
                "content_url": article.get("content_url"),
                "content": article.get("content"),  # Raw HTML if already fetched
                "publication_id": article.get("publication_id"),
            }
            
            # Remove None values to keep JSON clean
            article_input = {k: v for k, v in article_input.items() if v is not None}
            article_inputs.append(article_input)
        
        return {
            "issue_id": issue_info.get("id", ""),
            "issue_title": issue_info.get("title", "Newsletter Digest"),
            "issue_description": issue_info.get("description", ""),
            "articles": article_inputs,
            "layout_type": layout_type
        }
    
    def _execute_go_cli(
        self, 
        json_path: Path, 
        pdf_path: Path,
        keep_html: bool = False,
        timeout: int = None
    ) -> subprocess.CompletedProcess:
        """
        Execute the Go CLI to generate PDF.
        
        Args:
            json_path: Path to JSON input file
            pdf_path: Path where PDF should be written
            keep_html: Whether to keep intermediate HTML file
            timeout: Command timeout in seconds
            
        Returns:
            CompletedProcess object with returncode, stdout, stderr
        """
        timeout = timeout or self.default_timeout
        
        if self.use_docker:
            # Call via docker exec as root to avoid permission issues with /shared volume
            cmd = [
                "docker", "exec", "--user", "root", self.go_container_name,
                self.go_binary_path,
                "--articles-json", str(json_path),
                "--output", str(pdf_path),
                "--cleanup-images=false",  # Let Go handle its own cleanup
            ]
            if keep_html:
                cmd.append("--keep-html")
        else:
            # Call directly (for local development)
            cmd = [
                self.go_binary_path,
                "--articles-json", str(json_path),
                "--output", str(pdf_path),
                "--cleanup-images=false",
            ]
            if keep_html:
                cmd.append("--keep-html")
        
        logger.info(f"Executing Go CLI: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False  # Don't raise on non-zero exit
            )
            
            # Log output for debugging
            if result.stdout:
                logger.info(f"Go CLI stdout:\n{result.stdout}")
            if result.stderr:
                logger.warning(f"Go CLI stderr:\n{result.stderr}")
            
            return result
            
        except subprocess.TimeoutExpired as e:
            logger.error(f"Go CLI execution timed out after {timeout}s")
            raise TimeoutError(f"PDF generation timed out after {timeout} seconds")
        except FileNotFoundError as e:
            logger.error(f"Go CLI binary not found: {e}")
            raise RuntimeError(f"Go PDF service not available: {e}")
        except Exception as e:
            logger.error(f"Unexpected error executing Go CLI: {e}")
            raise
    
    async def generate_pdf_from_issue(
        self,
        issue_id: str,
        articles: List[Dict],
        issue_info: Dict,
        output_filename: Optional[str] = None,
        layout_type: str = "newspaper",
        keep_html: bool = False,
        timeout: int = None,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a PDF from issue articles using the Go CLI.
        
        Args:
            issue_id: UUID of the issue
            articles: List of article dictionaries with content
            issue_info: Issue metadata dictionary
            output_filename: Custom output filename (without extension)
            layout_type: Layout type ("essay" or "newspaper")
            keep_html: Whether to keep the intermediate HTML file for debugging
            timeout: Command timeout in seconds
            verbose: Enable verbose logging
            
        Returns:
            dict: Result dictionary with success status, URLs, and error info
        """
        result = {
            'success': False,
            'pdf_url': None,
            'html_path': None,
            'issue_info': issue_info,
            'articles_count': len(articles),
            'error': None
        }
        
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        json_path = None
        pdf_path = None
        html_path = None
        
        try:
            if not articles:
                result['error'] = "No articles provided"
                return result
            
            logger.info(f"Generating PDF for issue {issue_id} with {len(articles)} articles")
            
            # Generate temporary file paths
            json_path, pdf_path = self._generate_temp_paths()
            
            # HTML file will have same name as PDF but with .html extension
            if keep_html:
                html_path = pdf_path.with_suffix('.html')
            
            # Prepare article JSON
            article_json = self._prepare_article_json(articles, issue_info, layout_type)
            
            # Write JSON to shared volume
            logger.debug(f"Writing article data to: {json_path}")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(article_json, f, indent=2, ensure_ascii=False)
            
            # Execute Go CLI
            logger.info("Calling Go PDF generator...")
            cli_result = self._execute_go_cli(json_path, pdf_path, keep_html, timeout)
            
            # Check if command succeeded
            if cli_result.returncode != 0:
                error_msg = f"Go CLI failed with exit code {cli_result.returncode}"
                if cli_result.stderr:
                    error_msg += f": {cli_result.stderr}"
                result['error'] = error_msg
                logger.error(error_msg)
                return result
            
            # Check if PDF was created
            if not pdf_path.exists():
                result['error'] = "PDF file was not created by Go service"
                logger.error(result['error'])
                return result
            
            # Read generated PDF
            logger.info(f"Reading generated PDF: {pdf_path}")
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            
            logger.info(f"PDF size: {len(pdf_bytes)} bytes")
            
            # Generate output filename if not provided
            if not output_filename:
                safe_title = "".join(c for c in issue_info.get('title', 'newsletter') 
                                   if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = safe_title.replace(' ', '_')[:20]
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                output_filename = f"{safe_title}_{timestamp}"
            
            # Upload to Supabase storage
            logger.info("Uploading PDF to Supabase...")
            supabase_url = self.storage_service.upload_pdf(pdf_bytes, output_filename)
            
            result.update({
                'success': True,
                'pdf_url': supabase_url,
                'layout_type': layout_type
            })
            
            # If keep_html is true and HTML exists, add its path to result
            if keep_html and html_path and html_path.exists():
                result['html_path'] = str(html_path)
                logger.info(f"HTML file kept at: {html_path}")
            
            logger.info(f"PDF uploaded successfully: {supabase_url}")
            
        except TimeoutError as e:
            result['error'] = str(e)
            logger.error(f"Timeout error: {e}")
        except Exception as e:
            result['error'] = f"PDF generation failed: {str(e)}"
            logger.error(f"Error generating PDF: {e}", exc_info=True)
        finally:
            # Cleanup temporary files (but keep HTML if requested)
            files_to_cleanup = [json_path, pdf_path]
            if not keep_html and html_path:
                files_to_cleanup.append(html_path)
            self._cleanup_temp_files(*[f for f in files_to_cleanup if f is not None])
        
        return result
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test if the Go PDF service is accessible.
        
        Returns:
            dict: Connection test results
        """
        try:
            if self.use_docker:
                # Test docker exec
                result = subprocess.run(
                    ["docker", "exec", self.go_container_name, "echo", "test"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    return {
                        "success": True,
                        "message": f"Go PDF service is accessible (container: {self.go_container_name})",
                        "mode": "docker"
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Cannot access container: {self.go_container_name}",
                        "error": result.stderr,
                        "mode": "docker"
                    }
            else:
                # Test direct binary access
                if Path(self.go_binary_path).exists():
                    return {
                        "success": True,
                        "message": f"Go binary is accessible: {self.go_binary_path}",
                        "mode": "direct"
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Go binary not found: {self.go_binary_path}",
                        "mode": "direct"
                    }
        except Exception as e:
            return {
                "success": False,
                "message": "Go PDF service connection test failed",
                "error": str(e)
            }
