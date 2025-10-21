"""
ReportLab PDF Service Module
Alternative PDF generation using ReportLab instead of WeasyPrint.
Provides programmatic PDF creation with better control over layout and styling.
"""

import os
import io
import re
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import tempfile
import logging
import gc
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image as PILImage

# ReportLab imports
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm, cm
from reportlab.lib.colors import Color, black, blue, grey
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, 
    PageBreak, Table, TableStyle, KeepTogether, FrameBreak
)
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from services.rss_service import RSSService
from services.storage_service import StorageService
from utils.image_optimizer import ImageOptimizer, MemoryEfficientCache
from utils.memory_manager import (
    memory_manager, 
    memory_tracked, 
    memory_managed_operation,
    MemoryEfficientProcessor,
    get_memory_stats
)
from config.memory_settings import memory_settings

logger = logging.getLogger(__name__)

class ReportLabPDFService:
    """PDF Service using ReportLab for programmatic PDF generation"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.images_dir = self.base_dir / "images"
        self.newspapers_dir = self.base_dir / "newspapers"
        self.output_dir = self.newspapers_dir
        
        self.rss_service = RSSService()
        self.storage_service = StorageService()
        
        # Initialize image processing components
        self.image_optimizer = ImageOptimizer()
        self.image_cache = MemoryEfficientCache(self.images_dir)
        
        # Register cleanup callbacks with memory manager
        memory_manager.register_cleanup_callback(self._emergency_cleanup)
        
        # Ensure directories exist
        self.images_dir.mkdir(exist_ok=True)
        self.newspapers_dir.mkdir(exist_ok=True)
        
        # Initialize ReportLab styles
        self._setup_styles()
    
    def _setup_styles(self):
        """Initialize ReportLab paragraph styles for different layouts"""
        self.styles = getSampleStyleSheet()
        
        # Newspaper styles
        self.styles.add(ParagraphStyle(
            name='NewspaperTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=6,
            textColor=black,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='NewspaperHeadline',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceBefore=12,
            spaceAfter=6,
            textColor=black,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
            leftIndent=0,
            rightIndent=0
        ))
        
        self.styles.add(ParagraphStyle(
            name='NewspaperByline',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=8,
            textColor=grey,
            alignment=TA_LEFT,
            fontName='Helvetica-Oblique'
        ))
        
        self.styles.add(ParagraphStyle(
            name='NewspaperBody',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=13,
            spaceAfter=6,
            textColor=black,
            alignment=TA_JUSTIFY,
            fontName='Times-Roman',
            leftIndent=0,
            rightIndent=0
        ))
        
        # Essay styles
        self.styles.add(ParagraphStyle(
            name='EssayTitle',
            parent=self.styles['Title'],
            fontSize=20,
            spaceAfter=12,
            textColor=black,
            alignment=TA_CENTER,
            fontName='Times-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='EssayHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=18,
            spaceAfter=8,
            textColor=black,
            alignment=TA_LEFT,
            fontName='Times-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='EssayBody',
            parent=self.styles['Normal'],
            fontSize=12,
            leading=16,
            spaceAfter=8,
            textColor=black,
            alignment=TA_JUSTIFY,
            fontName='Times-Roman',
            leftIndent=0,
            rightIndent=0,
            firstLineIndent=0.25*inch
        ))
        
        # Common styles
        self.styles.add(ParagraphStyle(
            name='DateStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=12,
            textColor=grey,
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))
        
        self.styles.add(ParagraphStyle(
            name='Caption',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceAfter=6,
            textColor=grey,
            alignment=TA_CENTER,
            fontName='Helvetica-Oblique'
        ))
    
    def _emergency_cleanup(self) -> Dict[str, Any]:
        """Emergency cleanup callback for memory manager"""
        try:
            # Force cache cleanup
            cache_result = self.cleanup_image_cache(force=True)
            
            return {
                'cache_cleanup': cache_result,
                'reportlab_cleanup': True
            }
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")
            return {'error': str(e)}
    
    @memory_tracked("clean_html_content", force_gc=True)
    def clean_html_content(self, html_content: str, verbose: bool = False) -> str:
        """
        Clean HTML content by removing subscription widgets and social elements.
        Same implementation as the original service for consistency.
        """
        if verbose:
            logging.info("Cleaning HTML content...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove subscription widgets
        widgets_removed = 0
        for widget in soup.find_all('div', class_='subscription-widget-wrap-editor'):
            widget.decompose()
            widgets_removed += 1
        
        # Remove any forms (like subscription forms)
        forms_removed = 0
        for form in soup.find_all('form'):
            form.decompose()
            forms_removed += 1
        
        # Remove any input elements
        inputs_removed = 0
        for input_elem in soup.find_all('input'):
            input_elem.decompose()
            inputs_removed += 1
        
        # Remove social media and call-to-action elements
        social_elements_removed = 0
        social_selectors = [
            '[class*="share"]', '[class*="social"]', '[class*="like"]',
            '[class*="heart"]', '[class*="comment"]', '[class*="cta"]',
            '[class*="subscribe"]', '[class*="newsletter"]', 'footer', 'nav'
        ]
        
        for selector in social_selectors:
            for elem in soup.select(selector):
                elem.decompose()
                social_elements_removed += 1
        
        if verbose:
            logging.info(f"Cleaned HTML: {widgets_removed} widgets, {forms_removed} forms, "
                        f"{inputs_removed} inputs, {social_elements_removed} social elements removed")
        
        return str(soup)
    
    @memory_tracked("download_and_cache_images", force_gc=True)
    def download_and_cache_images(self, html_content: str, verbose: bool = False) -> Tuple[str, List[str]]:
        """
        Download and optimize images from HTML content, returning modified HTML and image paths.
        
        Returns:
            Tuple[str, List[str]]: Modified HTML content and list of local image paths
        """
        if verbose:
            logging.info("Processing images for ReportLab...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')
        image_paths = []
        
        if not images:
            if verbose:
                logging.info("No images found in content")
            return str(soup), image_paths
        
        processed_count = 0
        cached_count = 0
        failed_count = 0
        
        for img in images:
            src = img.get('src')
            if not src:
                continue
            
            try:
                # Check if image should be processed
                if not self.image_optimizer.should_process_image(url=src):
                    img.decompose()  # Remove from HTML since we can't process it
                    continue
                
                # Check cache first
                cached_path = self.image_cache.get_cached_path(src)
                if cached_path and cached_path.exists():
                    image_paths.append(str(cached_path))
                    # Mark image in HTML with a data attribute for later processing
                    img['data-local-path'] = str(cached_path)
                    cached_count += 1
                    continue
                
                # Download and optimize image
                if verbose:
                    logging.info(f"Downloading image: {src}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = requests.get(src, headers=headers, timeout=10, stream=True)
                response.raise_for_status()
                
                # Check content length
                content_length = response.headers.get('content-length')
                if content_length:
                    content_length = int(content_length)
                    if not self.image_optimizer.should_process_image(content_length, src):
                        img.decompose()
                        continue
                
                # Download image data
                image_data = b''
                downloaded_size = 0
                max_size = memory_settings.get_max_image_size_bytes()
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        if downloaded_size > max_size:
                            raise ValueError(f"Image too large: {downloaded_size} bytes")
                        image_data += chunk
                
                # Determine original format
                original_format = 'JPEG'
                content_type = response.headers.get('content-type', '').lower()
                if 'png' in content_type:
                    original_format = 'PNG'
                elif 'webp' in content_type:
                    original_format = 'WebP'
                elif 'gif' in content_type:
                    original_format = 'GIF'
                
                # Optimize image
                optimized_data, output_format = self.image_optimizer.optimize_image_stream(
                    image_data, original_format
                )
                
                # Cache optimized image
                extension = self.image_optimizer.get_file_extension(output_format)
                cached_path = self.image_cache.cache_image(src, optimized_data, extension)
                
                if cached_path:
                    image_paths.append(str(cached_path))
                    img['data-local-path'] = str(cached_path)
                    processed_count += 1
                else:
                    img.decompose()
                    failed_count += 1
                
            except Exception as e:
                if verbose:
                    logging.warning(f"Failed to process image {src}: {e}")
                failed_count += 1
                img.decompose()
        
        if verbose:
            logging.info(f"Image processing complete: {processed_count} processed, "
                        f"{cached_count} cached, {failed_count} failed")
        
        return str(soup), image_paths
    
    def _html_to_text_elements(self, html_content: str, style_prefix: str = 'Newspaper') -> List:
        """
        Convert HTML content to ReportLab flowable elements.
        
        Args:
            html_content: HTML content to convert
            style_prefix: Style prefix ('Newspaper' or 'Essay')
            
        Returns:
            List of ReportLab flowable elements
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = []
        
        # Process each element in the HTML
        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'img', 'ul', 'ol', 'li']):
            if element.name == 'img':
                # Handle images
                local_path = element.get('data-local-path')
                if local_path and Path(local_path).exists():
                    try:
                        # Get image dimensions and resize if needed
                        img_element = self._create_image_element(local_path)
                        if img_element:
                            elements.append(img_element)
                            
                            # Add caption if alt text exists
                            alt_text = element.get('alt', '').strip()
                            if alt_text:
                                caption = Paragraph(alt_text, self.styles['Caption'])
                                elements.append(caption)
                                elements.append(Spacer(1, 6))
                    except Exception as e:
                        logger.warning(f"Failed to add image {local_path}: {e}")
                
            elif element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # Handle headings
                text = element.get_text().strip()
                if text:
                    if style_prefix == 'Essay':
                        style = self.styles['EssayHeading']
                    else:
                        style = self.styles['NewspaperHeadline']
                    
                    elements.append(Paragraph(text, style))
            
            elif element.name in ['p', 'div']:
                # Handle paragraphs and divs
                text = element.get_text().strip()
                if text:
                    # Clean up text
                    text = re.sub(r'\s+', ' ', text)
                    
                    if style_prefix == 'Essay':
                        style = self.styles['EssayBody']
                    else:
                        style = self.styles['NewspaperBody']
                    
                    elements.append(Paragraph(text, style))
            
            elif element.name in ['ul', 'ol']:
                # Handle lists
                for li in element.find_all('li'):
                    text = li.get_text().strip()
                    if text:
                        text = re.sub(r'\s+', ' ', text)
                        bullet = "• " if element.name == 'ul' else "1. "
                        
                        if style_prefix == 'Essay':
                            style = self.styles['EssayBody']
                        else:
                            style = self.styles['NewspaperBody']
                        
                        elements.append(Paragraph(f"{bullet}{text}", style))
        
        return elements
    
    def _create_image_element(self, image_path: str, max_width: float = 4*inch, max_height: float = 3*inch) -> Optional[RLImage]:
        """
        Create a ReportLab Image element with proper sizing.
        
        Args:
            image_path: Path to the image file
            max_width: Maximum width in points
            max_height: Maximum height in points
            
        Returns:
            ReportLab Image element or None if failed
        """
        try:
            # Open image to get dimensions
            with PILImage.open(image_path) as pil_img:
                original_width, original_height = pil_img.size
            
            # Calculate scaling to fit within max dimensions while preserving aspect ratio
            width_scale = max_width / original_width
            height_scale = max_height / original_height
            scale = min(width_scale, height_scale, 1.0)  # Don't scale up
            
            new_width = original_width * scale
            new_height = original_height * scale
            
            # Create ReportLab Image
            img = RLImage(image_path, width=new_width, height=new_height)
            return img
            
        except Exception as e:
            logger.warning(f"Failed to create image element for {image_path}: {e}")
            return None
    
    @memory_tracked("generate_pdf_from_issue", force_gc=True)
    async def generate_pdf_from_issue(
        self, 
        issue_id: str, 
        days_back: int = 7,
        max_articles_per_publication: int = 5,
        layout_type: str = 'newspaper',
        output_filename: Optional[str] = None,
        keep_html: bool = False,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a PDF from an issue's articles using ReportLab.
        
        Args:
            issue_id (str): UUID of the issue
            days_back (int): Number of days to look back for articles
            max_articles_per_publication (int): Maximum articles per publication
            layout_type (str): Layout type ('newspaper' or 'essay')
            output_filename (str, optional): Custom output filename
            keep_html (bool): Whether to keep the intermediate HTML file (for debugging)
            verbose (bool): Enable verbose output
            
        Returns:
            dict: Result dictionary with success status, URLs, and error info
        """
        result = {
            'success': False,
            'pdf_url': None,
            'html_path': None,
            'issue_info': None,
            'articles_count': 0,
            'error': None
        }
        
        try:
            if verbose:
                logging.info(f"Generating ReportLab PDF for issue {issue_id}")
            
            # Fetch articles for the issue
            articles_data = await self.rss_service.fetch_recent_articles_for_issue(
                issue_id, 
                days_back=days_back,
                max_articles_per_publication=max_articles_per_publication
            )
            
            if not articles_data or articles_data['total_articles'] == 0:
                result['error'] = "No articles found for the specified issue and date range"
                return result
            
            issue_info = articles_data['issue']
            
            # Prepare articles for rendering
            articles = []
            for pub_id, pub_articles in articles_data['articles_by_publication'].items():
                for article in pub_articles:
                    # Get full content for each article
                    if article.get('content_url'):
                        try:
                            content = self._fetch_article_content(article['content_url'])
                            if content:
                                cleaned_content = self.clean_html_content(content, verbose)
                                processed_content, image_paths = self.download_and_cache_images(cleaned_content, verbose)
                                article['content'] = processed_content
                                article['image_paths'] = image_paths
                                articles.append(article)
                        except Exception as e:
                            if verbose:
                                logging.warning(f"Failed to fetch content for {article['title']}: {e}")
            
            if not articles:
                result['error'] = "No article content could be fetched"
                return result
            
            # Generate output filename
            if not output_filename:
                safe_title = "".join(c for c in issue_info['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = safe_title.replace(' ', '_')[:20]
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                output_filename = f"{safe_title}_{timestamp}_reportlab"
            
            # Generate PDF using ReportLab
            if verbose:
                logging.info(f"Generating ReportLab PDF: {output_filename}.pdf")
            
            # Use advanced layout if available
            try:
                pdf_bytes = self.create_advanced_pdf(
                    articles=articles,
                    issue_info=issue_info,
                    layout_type=layout_type,
                    verbose=verbose
                )
            except Exception as e:
                if verbose:
                    logging.warning(f"Advanced layout failed, falling back to simple layout: {e}")
                # Fallback to simple document creation
                pdf_bytes = self._create_pdf_document(
                    articles=articles,
                    issue_info=issue_info,
                    layout_type=layout_type,
                    verbose=verbose
                )
            
            # Upload to Supabase storage
            supabase_url = self.storage_service.upload_pdf(pdf_bytes, output_filename)
            
            result.update({
                'success': True,
                'pdf_url': supabase_url,
                'issue_info': issue_info,
                'articles_count': len(articles),
                'layout_type': layout_type
            })
            
            if verbose:
                logging.info(f"ReportLab PDF uploaded successfully to Supabase: {supabase_url}")
            
        except Exception as e:
            result['error'] = f"ReportLab PDF generation failed: {str(e)}"
            if verbose:
                logging.error(f"ReportLab PDF generation error: {e}")
        
        return result
    
    def _fetch_article_content(self, url: str) -> Optional[str]:
        """
        Fetch the full content of an article from its URL.
        Same implementation as the original service for consistency.
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse the HTML and extract the main content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to find the main article content
            content_selectors = [
                'article',
                '.post-content',
                '.article-content',
                '.entry-content',
                '[class*="content"]',
                'main'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    return str(content_elem)
            
            # Fallback to body content
            body = soup.find('body')
            if body:
                return str(body)
            
            return None
            
        except Exception as e:
            logging.warning(f"Failed to fetch article content from {url}: {e}")
            return None
    
    def _create_pdf_document(
        self, 
        articles: List[Dict], 
        issue_info: Dict,
        layout_type: str = 'newspaper',
        verbose: bool = False
    ) -> bytes:
        """
        Create the PDF document using ReportLab.
        
        Args:
            articles: List of article dictionaries
            issue_info: Issue information
            layout_type: Layout type ('newspaper' or 'essay')
            verbose: Enable verbose output
            
        Returns:
            bytes: PDF document as bytes
        """
        if verbose:
            logging.info(f"Creating {layout_type} PDF with {len(articles)} articles")
        
        # Create a BytesIO buffer for the PDF
        buffer = io.BytesIO()
        
        # Set up document with appropriate page size and margins
        if layout_type == 'newspaper':
            pagesize = letter
            margins = {
                'leftMargin': 0.75*inch,
                'rightMargin': 0.75*inch,
                'topMargin': 1*inch,
                'bottomMargin': 0.75*inch
            }
        else:  # essay
            pagesize = letter
            margins = {
                'leftMargin': 1*inch,
                'rightMargin': 1*inch,
                'topMargin': 1*inch,
                'bottomMargin': 1*inch
            }
        
        # Create the document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=pagesize,
            **margins
        )
        
        # Build the story (content)
        story = []
        
        # Add title page
        story.extend(self._create_title_page(issue_info, layout_type))
        
        # Add articles
        for i, article in enumerate(articles):
            if verbose:
                logging.info(f"Processing article {i+1}/{len(articles)}: {article.get('title', 'Untitled')}")
            
            # Add page break between articles (except for the first one)
            if i > 0 and layout_type == 'essay':
                story.append(PageBreak())
            elif i > 0 and layout_type == 'newspaper':
                story.append(Spacer(1, 0.5*inch))
            
            # Add article content
            article_elements = self._create_article_elements(article, layout_type)
            story.extend(article_elements)
        
        # Build the PDF
        doc.build(story)
        
        # Get the PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    def _create_title_page(self, issue_info: Dict, layout_type: str) -> List:
        """
        Create title page elements for the PDF.
        
        Args:
            issue_info: Issue information dictionary
            layout_type: Layout type ('newspaper' or 'essay')
            
        Returns:
            List of ReportLab flowable elements
        """
        elements = []
        
        # Add some space at the top
        elements.append(Spacer(1, 0.5*inch))
        
        # Issue title
        title = issue_info.get('title', 'Newsletter Digest')
        if layout_type == 'newspaper':
            title_style = self.styles['NewspaperTitle']
        else:
            title_style = self.styles['EssayTitle']
        
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Date
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        elements.append(Paragraph(current_date, self.styles['DateStyle']))
        elements.append(Spacer(1, 0.5*inch))
        
        # Issue description if available
        description = issue_info.get('description', '')
        if description:
            if layout_type == 'newspaper':
                desc_style = self.styles['NewspaperBody']
            else:
                desc_style = self.styles['EssayBody']
            
            elements.append(Paragraph(description, desc_style))
            elements.append(Spacer(1, 0.5*inch))
        
        return elements
    
    def _create_article_elements(self, article: Dict, layout_type: str) -> List:
        """
        Create ReportLab elements for a single article.
        
        Args:
            article: Article dictionary
            layout_type: Layout type ('newspaper' or 'essay')
            
        Returns:
            List of ReportLab flowable elements
        """
        elements = []
        
        # Article title
        title = article.get('title', 'Untitled Article')
        if layout_type == 'newspaper':
            title_style = self.styles['NewspaperHeadline']
        else:
            title_style = self.styles['EssayHeading']
        
        elements.append(Paragraph(title, title_style))
        
        # Byline (author and date)
        byline_parts = []
        author = article.get('author', '')
        if author:
            byline_parts.append(f"By {author}")
        
        date_published = article.get('date_published', '')
        if date_published:
            # Try to format the date nicely
            try:
                # Assume ISO format and convert to readable format
                from datetime import datetime
                if 'T' in date_published:
                    dt = datetime.fromisoformat(date_published.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%B %d, %Y")
                    byline_parts.append(formatted_date)
                else:
                    byline_parts.append(date_published)
            except:
                byline_parts.append(date_published)
        
        if byline_parts:
            byline = " | ".join(byline_parts)
            if layout_type == 'newspaper':
                byline_style = self.styles['NewspaperByline']
            else:
                byline_style = self.styles['NewspaperByline']  # Use same style for both
            
            elements.append(Paragraph(byline, byline_style))
        
        # Article content
        content = article.get('content', '')
        if content:
            # Convert HTML content to ReportLab elements
            content_elements = self._html_to_text_elements(content, layout_type.title())
            elements.extend(content_elements)
        
        # Add some space after the article
        elements.append(Spacer(1, 0.25*inch))
        
        return elements
    
    def get_image_cache_stats(self) -> Dict[str, Any]:
        """Get current image cache statistics"""
        return self.image_cache.get_stats()
    
    def cleanup_image_cache(self, force: bool = False) -> Dict[str, Any]:
        """
        Clean up image cache
        
        Args:
            force: If True, clear entire cache. If False, use normal cleanup rules.
            
        Returns:
            Dict with cleanup statistics
        """
        stats_before = self.image_cache.get_stats()
        
        if force:
            self.image_cache.clear_all()
            stats_after = self.image_cache.get_stats()
            return {
                'action': 'full_clear',
                'files_removed': stats_before['total_files'],
                'size_freed_mb': stats_before['total_size_mb']
            }
        else:
            # Normal cleanup based on cache limits
            self.image_cache._cleanup_cache()
            stats_after = self.image_cache.get_stats()
            
            files_removed = stats_before['total_files'] - stats_after['total_files']
            size_freed = stats_before['total_size_mb'] - stats_after['total_size_mb']
            
            return {
                'action': 'smart_cleanup',
                'files_removed': files_removed,
                'size_freed_mb': size_freed,
                'files_remaining': stats_after['total_files'],
                'size_remaining_mb': stats_after['total_size_mb']
            }
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics"""
        return get_memory_stats()
    
    def force_memory_cleanup(self) -> Dict[str, Any]:
        """Force memory cleanup and garbage collection"""
        return memory_manager.force_garbage_collection("manual_reportlab_pdf_service_cleanup")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service-specific statistics including memory and cache"""
        memory_stats = self.get_memory_stats()
        cache_stats = self.get_image_cache_stats()
        
        return {
            'memory': memory_stats,
            'image_cache': cache_stats,
            'pdf_engine': 'ReportLab',
            'settings': {
                'max_image_size_mb': memory_settings.MAX_IMAGE_SIZE_MB,
                'max_cache_size_mb': memory_settings.MAX_CACHE_SIZE_MB,
                'max_article_length': memory_settings.MAX_ARTICLE_LENGTH,
                'image_compression_enabled': memory_settings.ENABLE_IMAGE_COMPRESSION,
                'webp_conversion_enabled': memory_settings.ENABLE_WEBP_CONVERSION
            }
        }
    
    # Advanced layout methods
    
    def _create_newspaper_layout_document(
        self, 
        articles: List[Dict], 
        issue_info: Dict,
        verbose: bool = False
    ) -> bytes:
        """
        Create a newspaper-style PDF with multi-column layout using ReportLab's advanced features.
        
        Args:
            articles: List of article dictionaries
            issue_info: Issue information
            verbose: Enable verbose output
            
        Returns:
            bytes: PDF document as bytes
        """
        if verbose:
            logging.info("Creating advanced newspaper layout PDF")
        
        buffer = io.BytesIO()
        
        # Custom page template for newspaper layout
        doc = BaseDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        # Define frames for multi-column layout
        frame_width = (letter[0] - 1*inch) / 2 - 0.125*inch  # Two columns with gap
        frame_height = letter[1] - 1.5*inch
        
        # Left column frame
        left_frame = Frame(
            0.5*inch, 0.75*inch,
            frame_width, frame_height,
            leftPadding=6, rightPadding=6,
            topPadding=6, bottomPadding=6,
            id='left_column'
        )
        
        # Right column frame  
        right_frame = Frame(
            0.5*inch + frame_width + 0.25*inch, 0.75*inch,
            frame_width, frame_height,
            leftPadding=6, rightPadding=6,
            topPadding=6, bottomPadding=6,
            id='right_column'
        )
        
        # Create page template with frames
        page_template = PageTemplate(
            id='newspaper',
            frames=[left_frame, right_frame],
            onPage=self._newspaper_header_footer
        )
        
        doc.addPageTemplates([page_template])
        
        # Build story
        story = []
        
        # Title spans full width
        story.append(self._create_newspaper_header(issue_info))
        story.append(FrameBreak())  # Move to next frame (left column)
        
        # Add articles to columns
        for i, article in enumerate(articles):
            if verbose:
                logging.info(f"Adding article {i+1} to newspaper layout: {article.get('title', 'Untitled')}")
            
            article_elements = self._create_compact_article_elements(article)
            story.extend(article_elements)
            
            # Add separator between articles
            if i < len(articles) - 1:
                story.append(Spacer(1, 12))
                story.append(self._create_article_separator())
                story.append(Spacer(1, 12))
        
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
    
    def _create_newspaper_header(self, issue_info: Dict) -> KeepTogether:
        """Create a newspaper-style header that spans the full page width"""
        elements = []
        
        # Main title
        title = issue_info.get('title', 'Newsletter Digest')
        elements.append(Paragraph(title, self.styles['NewspaperTitle']))
        
        # Date and edition info
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        elements.append(Paragraph(current_date, self.styles['DateStyle']))
        
        # Add horizontal line
        from reportlab.platypus import HRFlowable
        elements.append(Spacer(1, 6))
        elements.append(HRFlowable(width="100%", thickness=1, color=black))
        elements.append(Spacer(1, 12))
        
        return KeepTogether(elements)
    
    def _create_compact_article_elements(self, article: Dict) -> List:
        """Create compact article elements suitable for newspaper columns"""
        elements = []
        
        # Compact title
        title = article.get('title', 'Untitled Article')
        compact_title_style = ParagraphStyle(
            'CompactTitle',
            parent=self.styles['NewspaperHeadline'],
            fontSize=12,
            spaceBefore=0,
            spaceAfter=4,
            leftIndent=0,
            rightIndent=0
        )
        elements.append(Paragraph(f"<b>{title}</b>", compact_title_style))
        
        # Compact byline
        byline_parts = []
        author = article.get('author', '')
        if author:
            byline_parts.append(f"By {author}")
        
        if byline_parts:
            byline = " | ".join(byline_parts)
            compact_byline_style = ParagraphStyle(
                'CompactByline',
                parent=self.styles['NewspaperByline'],
                fontSize=8,
                spaceAfter=6
            )
            elements.append(Paragraph(byline, compact_byline_style))
        
        # Compact content - just first paragraph or summary
        content = article.get('content', '')
        if content:
            # Extract first paragraph or create summary
            soup = BeautifulSoup(content, 'html.parser')
            first_para = soup.find('p')
            
            if first_para:
                text = first_para.get_text().strip()
                # Truncate if too long
                if len(text) > 300:
                    text = text[:297] + "..."
                
                compact_body_style = ParagraphStyle(
                    'CompactBody',
                    parent=self.styles['NewspaperBody'],
                    fontSize=9,
                    leading=11,
                    spaceAfter=4
                )
                elements.append(Paragraph(text, compact_body_style))
        
        return elements
    
    def _create_article_separator(self):
        """Create a visual separator between articles"""
        from reportlab.platypus import HRFlowable
        return HRFlowable(width="80%", thickness=0.5, color=grey, hAlign='CENTER')
    
    def _newspaper_header_footer(self, canvas, doc):
        """Add header and footer to newspaper pages"""
        canvas.saveState()
        
        # Header - page number
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(
            letter[0] - 0.5*inch, 
            letter[1] - 0.5*inch,
            f"Page {doc.page}"
        )
        
        # Footer - generation info
        canvas.drawString(
            0.5*inch, 
            0.5*inch,
            f"Generated by Newsletter2Paper • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        canvas.restoreState()
    
    def _create_essay_layout_document(
        self, 
        articles: List[Dict], 
        issue_info: Dict,
        verbose: bool = False
    ) -> bytes:
        """
        Create an essay-style PDF with single-column academic layout.
        
        Args:
            articles: List of article dictionaries
            issue_info: Issue information
            verbose: Enable verbose output
            
        Returns:
            bytes: PDF document as bytes
        """
        if verbose:
            logging.info("Creating essay layout PDF")
        
        buffer = io.BytesIO()
        
        # Create document with academic-style margins
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=1.25*inch,
            rightMargin=1.25*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )
        
        story = []
        
        # Title page
        story.extend(self._create_essay_title_page(issue_info))
        story.append(PageBreak())
        
        # Table of contents
        story.extend(self._create_table_of_contents(articles))
        story.append(PageBreak())
        
        # Articles
        for i, article in enumerate(articles):
            if verbose:
                logging.info(f"Adding article {i+1} to essay layout: {article.get('title', 'Untitled')}")
            
            # Add article with academic formatting
            article_elements = self._create_academic_article_elements(article)
            story.extend(article_elements)
            
            # Page break between articles
            if i < len(articles) - 1:
                story.append(PageBreak())
        
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
    
    def _create_essay_title_page(self, issue_info: Dict) -> List:
        """Create an academic-style title page"""
        elements = []
        
        # Center the content vertically
        elements.append(Spacer(1, 2*inch))
        
        # Main title
        title = issue_info.get('title', 'Newsletter Digest')
        title_style = ParagraphStyle(
            'EssayTitlePage',
            parent=self.styles['EssayTitle'],
            fontSize=28,
            spaceAfter=0.5*inch,
            alignment=TA_CENTER
        )
        elements.append(Paragraph(title, title_style))
        
        # Subtitle
        subtitle = issue_info.get('description', 'A Curated Collection of Articles')
        subtitle_style = ParagraphStyle(
            'EssaySubtitle',
            parent=self.styles['EssayBody'],
            fontSize=16,
            spaceAfter=1*inch,
            alignment=TA_CENTER,
            fontName='Times-Italic'
        )
        elements.append(Paragraph(subtitle, subtitle_style))
        
        # Date
        current_date = datetime.now().strftime("%B %d, %Y")
        date_style = ParagraphStyle(
            'EssayDate',
            parent=self.styles['EssayBody'],
            fontSize=14,
            alignment=TA_CENTER
        )
        elements.append(Paragraph(current_date, date_style))
        
        return elements
    
    def _create_table_of_contents(self, articles: List[Dict]) -> List:
        """Create a table of contents for the essay layout"""
        elements = []
        
        # TOC Title
        toc_title_style = ParagraphStyle(
            'TOCTitle',
            parent=self.styles['EssayHeading'],
            fontSize=18,
            spaceAfter=0.5*inch,
            alignment=TA_CENTER
        )
        elements.append(Paragraph("Table of Contents", toc_title_style))
        
        # TOC entries
        toc_style = ParagraphStyle(
            'TOCEntry',
            parent=self.styles['EssayBody'],
            fontSize=12,
            spaceAfter=8,
            leftIndent=0.25*inch
        )
        
        for i, article in enumerate(articles, 1):
            title = article.get('title', f'Article {i}')
            # Simple TOC entry - in a real implementation you'd track page numbers
            elements.append(Paragraph(f"{i}. {title}", toc_style))
        
        return elements
    
    def _create_academic_article_elements(self, article: Dict) -> List:
        """Create academic-style article elements"""
        elements = []
        
        # Article title
        title = article.get('title', 'Untitled Article')
        elements.append(Paragraph(title, self.styles['EssayHeading']))
        
        # Author and source info
        byline_parts = []
        author = article.get('author', '')
        if author:
            byline_parts.append(f"By {author}")
        
        source = article.get('publication_name', '')
        if source:
            byline_parts.append(f"Source: {source}")
        
        if byline_parts:
            byline = " | ".join(byline_parts)
            academic_byline_style = ParagraphStyle(
                'AcademicByline',
                parent=self.styles['EssayBody'],
                fontSize=10,
                spaceAfter=0.25*inch,
                fontName='Times-Italic',
                textColor=grey
            )
            elements.append(Paragraph(byline, academic_byline_style))
        
        # Full article content
        content = article.get('content', '')
        if content:
            content_elements = self._html_to_text_elements(content, 'Essay')
            elements.extend(content_elements)
        
        return elements
    
    def create_advanced_pdf(
        self,
        articles: List[Dict],
        issue_info: Dict,
        layout_type: str = 'newspaper',
        verbose: bool = False
    ) -> bytes:
        """
        Create PDF using advanced layout features.
        
        Args:
            articles: List of article dictionaries  
            issue_info: Issue information
            layout_type: 'newspaper' for multi-column or 'essay' for academic style
            verbose: Enable verbose output
            
        Returns:
            bytes: PDF document as bytes
        """
        if layout_type == 'newspaper':
            return self._create_newspaper_layout_document(articles, issue_info, verbose)
        else:
            return self._create_essay_layout_document(articles, issue_info, verbose)
    
    # Utility and compatibility methods
    
    async def generate_pdf_from_articles(
        self,
        articles: List[Dict],
        issue_title: str = "Newsletter Digest",
        layout_type: str = 'newspaper',
        output_filename: Optional[str] = None,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Generate PDF directly from a list of articles (without fetching from RSS).
        Useful for testing or when articles are already available.
        
        Args:
            articles: List of article dictionaries with 'title', 'content', etc.
            issue_title: Title for the issue
            layout_type: 'newspaper' or 'essay'
            output_filename: Custom filename
            verbose: Enable verbose output
            
        Returns:
            dict: Result dictionary with success status and URLs
        """
        result = {
            'success': False,
            'pdf_url': None,
            'articles_count': 0,
            'error': None
        }
        
        try:
            if not articles:
                result['error'] = "No articles provided"
                return result
            
            # Process articles content
            processed_articles = []
            for article in articles:
                content = article.get('content', '')
                if content:
                    # Clean and process content
                    cleaned_content = self.clean_html_content(content, verbose)
                    processed_content, image_paths = self.download_and_cache_images(cleaned_content, verbose)
                    article['content'] = processed_content
                    article['image_paths'] = image_paths
                
                processed_articles.append(article)
            
            # Create issue info
            issue_info = {
                'title': issue_title,
                'description': f"Collection of {len(processed_articles)} articles"
            }
            
            # Generate filename
            if not output_filename:
                safe_title = "".join(c for c in issue_title if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = safe_title.replace(' ', '_')[:20]
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                output_filename = f"{safe_title}_{timestamp}_reportlab"
            
            # Generate PDF
            if verbose:
                logging.info(f"Generating PDF from {len(processed_articles)} articles")
            
            pdf_bytes = self.create_advanced_pdf(
                articles=processed_articles,
                issue_info=issue_info,
                layout_type=layout_type,
                verbose=verbose
            )
            
            # Upload to Supabase storage
            supabase_url = self.storage_service.upload_pdf(pdf_bytes, output_filename)
            
            result.update({
                'success': True,
                'pdf_url': supabase_url,
                'articles_count': len(processed_articles),
                'layout_type': layout_type
            })
            
            if verbose:
                logging.info(f"PDF generated successfully: {supabase_url}")
            
        except Exception as e:
            result['error'] = f"PDF generation from articles failed: {str(e)}"
            if verbose:
                logging.error(f"PDF generation error: {e}")
        
        return result
    
    def preview_pdf_structure(
        self,
        articles: List[Dict],
        issue_info: Dict,
        layout_type: str = 'newspaper'
    ) -> Dict[str, Any]:
        """
        Preview the structure of a PDF without generating it.
        Useful for debugging and understanding content organization.
        
        Args:
            articles: List of article dictionaries
            issue_info: Issue information
            layout_type: Layout type
            
        Returns:
            dict: Structure information
        """
        structure = {
            'layout_type': layout_type,
            'total_articles': len(articles),
            'estimated_pages': 0,
            'articles': [],
            'has_images': False,
            'total_content_length': 0
        }
        
        # Analyze articles
        for i, article in enumerate(articles):
            article_info = {
                'index': i + 1,
                'title': article.get('title', f'Article {i+1}'),
                'author': article.get('author', 'Unknown'),
                'content_length': len(article.get('content', '')),
                'has_images': len(article.get('image_paths', [])) > 0,
                'image_count': len(article.get('image_paths', []))
            }
            
            structure['articles'].append(article_info)
            structure['total_content_length'] += article_info['content_length']
            
            if article_info['has_images']:
                structure['has_images'] = True
        
        # Rough page estimation (very approximate)
        chars_per_page = 2500 if layout_type == 'newspaper' else 2000
        estimated_text_pages = max(1, structure['total_content_length'] // chars_per_page)
        image_pages = sum(max(1, art['image_count'] // 4) for art in structure['articles'])
        structure['estimated_pages'] = estimated_text_pages + image_pages + 2  # +2 for title/toc
        
        return structure
    
    def get_supported_features(self) -> Dict[str, Any]:
        """
        Get information about supported features in this ReportLab implementation.
        
        Returns:
            dict: Feature support information
        """
        return {
            'pdf_engine': 'ReportLab',
            'version': 'Newsletter2Paper ReportLab Service v1.0',
            'supported_layouts': ['newspaper', 'essay'],
            'features': {
                'multi_column_layout': True,
                'image_embedding': True,
                'image_optimization': True,
                'memory_management': True,
                'html_content_cleaning': True,
                'table_of_contents': True,
                'custom_fonts': False,  # Could be added
                'custom_page_sizes': True,
                'headers_footers': True,
                'advanced_styling': True
            },
            'image_formats': ['JPEG', 'PNG', 'WebP', 'GIF'],
            'max_image_size_mb': memory_settings.MAX_IMAGE_SIZE_MB,
            'max_cache_size_mb': memory_settings.MAX_CACHE_SIZE_MB,
            'limitations': [
                'Complex CSS layouts not directly supported',
                'JavaScript content not rendered',
                'Some HTML formatting may be simplified'
            ]
        }
