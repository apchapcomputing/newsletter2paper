"""
PDF Service Module
Handles conversion of article content to formatted PDFs.
"""

import os
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from weasyprint import HTML
from bs4 import BeautifulSoup
import tempfile
import logging
import gc
from typing import Dict, List, Optional, Any
from jinja2 import Environment, FileSystemLoader

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

class PDFService:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.images_dir = self.base_dir / "images"
        self.styles_dir = self.base_dir / "styles"
        self.newspapers_dir = self.base_dir / "newspapers"
        self.templates_dir = self.base_dir / "templates"
        self.output_dir = self.newspapers_dir  # Use newspapers dir as output directory
        
        self.rss_service = RSSService()
        self.storage_service = StorageService()
        
        # Initialize Jinja2 environment
        self.jinja_env = Environment(loader=FileSystemLoader(str(self.templates_dir)))
        
        # Initialize image processing components
        self.image_optimizer = ImageOptimizer()
        self.image_cache = MemoryEfficientCache(self.images_dir)
        
        # Register cleanup callbacks with memory manager
        memory_manager.register_cleanup_callback(self._emergency_cleanup)
        
        # Ensure directories exist
        self.images_dir.mkdir(exist_ok=True)
        self.newspapers_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(exist_ok=True)
    
    def _emergency_cleanup(self) -> Dict[str, Any]:
        """Emergency cleanup callback for memory manager"""
        try:
            # Force cache cleanup
            cache_result = self.cleanup_image_cache(force=True)
            
            # Clear Jinja environment cache if it exists
            if hasattr(self.jinja_env, 'cache') and self.jinja_env.cache:
                self.jinja_env.cache.clear()
            
            return {
                'cache_cleanup': cache_result,
                'jinja_cache_cleared': True
            }
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")
            return {'error': str(e)}
    
    @memory_tracked("clean_html_content", force_gc=True)
    def clean_html_content(self, html_content: str, verbose: bool = False) -> str:
        """
        Clean HTML content by removing subscription widgets and formatting footnotes.
        
        Args:
            html_content (str): Raw HTML content
            verbose (bool): Enable verbose output
            
        Returns:
            str: Cleaned HTML content
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
        
        # Remove any elements with subscription-related classes
        subscription_selectors = [
            '[class*="subscription"]',
            '[class*="subscribe"]',
            '[class*="email-input"]',
            '[data-component-name*="Subscribe"]'
        ]
        
        subscription_elements_removed = 0
        for selector in subscription_selectors:
            for elem in soup.select(selector):
                elem.decompose()
                subscription_elements_removed += 1
        
        # Remove image icons (expand and refresh buttons)
        image_icons_removed = 0
        image_control_selectors = [
            '.lucide-maximize2',
            '.lucide-refresh-cw'
        ]
        for selector in image_control_selectors:
            for elem in soup.select(selector):
                elem.decompose()
                image_icons_removed += 1
        
        # Remove social media and call-to-action elements
        social_elements_removed = 0
        social_selectors = [
            # Share buttons and social links
            '[class*="share"]',
            '[class*="social"]',
            '[data-action="share"]',
            '.share-button',
            '.social-button',
            '.social-media',
            '.share-link',
            
            # Like/heart buttons and counts
            '[class*="like"]',
            '[class*="heart"]',
            '[class*="favorite"]',
            '.like-button',
            '.heart-button',
            '.favorite-button',
            
            # Comment counts and buttons
            '[class*="comment"]',
            '.comment-count',
            '.comment-button',
            '.comments-section',
            
            # Generic call-to-action elements
            '[class*="cta"]',
            '[class*="call-to-action"]',
            '.cta-button',
            '.action-button',
            
            # Social platform specific
            '[class*="twitter"]',
            '[class*="facebook"]',
            '[class*="linkedin"]',
            '[class*="instagram"]',
            '[class*="tiktok"]',
            '[class*="youtube"]',
            
            # Newsletter/email signup
            '[class*="newsletter"]',
            '[class*="signup"]',
            '[class*="email-signup"]',
            
            # Interaction counters
            '[class*="view"]',
            '[class*="read"]',
            '.view-count',
            '.read-count',
            '.engagement',
            
            # Footer and navigation elements
            'footer',
            'nav',
            '[role="navigation"]',
            '.footer',
            '.navigation'
        ]
        
        for selector in social_selectors:
            for elem in soup.select(selector):
                elem.decompose()
                social_elements_removed += 1
        
        # Remove elements containing typical social/CTA text
        text_patterns_to_remove = [
            'share', 'like', 'comment', 'subscribe', 'follow',
            'sign up', 'join', 'newsletter', 'get updates'
        ]
        
        text_elements_removed = 0
        for element in soup.find_all(text=True):
            if element.parent.name in ['script', 'style']:
                continue
            
            element_text = element.strip().lower()
            for pattern in text_patterns_to_remove:
                if pattern in element_text and len(element_text) < 50:  # Only remove short text snippets
                    try:
                        element.parent.decompose()
                        text_elements_removed += 1
                        break
                    except:
                        pass
        
        if verbose:
            logging.info(f"Cleaned HTML: {widgets_removed} widgets, {forms_removed} forms, "
                        f"{inputs_removed} inputs, {subscription_elements_removed} subscription elements, "
                        f"{image_icons_removed} image icons, {social_elements_removed} social elements, "
                        f"{text_elements_removed} text elements removed")
        
        # Format footnotes to have number and content on same line
        footnotes = soup.find_all('div', class_='footnote')
        footnotes_formatted = 0
        
        for footnote in footnotes:
            footnote_number = footnote.find('a', class_='footnote-number')
            footnote_content = footnote.find('div', class_='footnote-content')
            
            if footnote_number and footnote_content:
                # Get the number text
                number_text = footnote_number.get_text().strip()
                
                # Get the content and its inner HTML
                content_p = footnote_content.find('p')
                if content_p:
                    # Create new inline footnote format
                    new_footnote = soup.new_tag('p', style='margin-bottom: 6px; text-indent: -1em; padding-left: 1em;')
                    
                    # Preserve the original footnote number as a linked element
                    footnote_number_copy = soup.new_tag(
                        'a',
                        href=footnote_number.get('href'),
                        id=footnote_number.get('id'),
                        target=footnote_number.get('target', '_self'),
                        style='font-weight: bold; text-decoration: none;'
                    )
                    footnote_number_copy.string = f"{number_text}. "
                    new_footnote.append(footnote_number_copy)
                    
                    # Add the content (preserving any links)
                    for content in list(content_p.contents):
                        if hasattr(content, 'name'):
                            new_footnote.append(content.extract())
                        else:
                            new_footnote.append(content)
                    
                    # Replace the original footnote with the new format
                    footnote.replace_with(new_footnote)
                    footnotes_formatted += 1
        
        if verbose:
            logging.info(f"Formatted {footnotes_formatted} footnotes")
        
        return str(soup)
    
    @memory_tracked("download_and_cache_images", force_gc=True)
    def download_and_cache_images(self, html_content: str, verbose: bool = False) -> str:
        """
        Download and optimize images from HTML content with memory-efficient caching.
        
        Args:
            html_content (str): HTML content containing image URLs
            verbose (bool): Enable verbose output
            
        Returns:
            str: Modified HTML content with local image paths
        """
        if verbose:
            logging.info("Processing images with optimization...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')
        
        if not images:
            if verbose:
                logging.info("No images found in content")
            return str(soup)
        
        processed_count = 0
        cached_count = 0
        failed_count = 0
        skipped_count = 0
        total_original_size = 0
        total_optimized_size = 0
        
        for img in images:
            src = img.get('src')
            if not src:
                continue
            
            try:
                # Check if image should be processed
                if not self.image_optimizer.should_process_image(url=src):
                    skipped_count += 1
                    continue
                
                # Check cache first
                cached_path = self.image_cache.get_cached_path(src)
                if cached_path:
                    img['src'] = str(cached_path)
                    cached_count += 1
                    if verbose:
                        logging.debug(f"Using cached image: {src}")
                    continue
                
                # Download and optimize image
                if verbose:
                    logging.info(f"Downloading and optimizing image: {src}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                # Stream download with size checking
                response = requests.get(src, headers=headers, timeout=10, stream=True)
                response.raise_for_status()
                
                # Check content length
                content_length = response.headers.get('content-length')
                if content_length:
                    content_length = int(content_length)
                    if not self.image_optimizer.should_process_image(content_length, src):
                        skipped_count += 1
                        img.decompose()  # Remove oversized images
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
                
                total_original_size += len(image_data)
                
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
                total_optimized_size += len(optimized_data)
                
                # Cache optimized image
                extension = self.image_optimizer.get_file_extension(output_format)
                cached_path = self.image_cache.cache_image(src, optimized_data, extension)
                
                # Update img src to local path
                img['src'] = str(cached_path)
                processed_count += 1
                
            except Exception as e:
                if verbose:
                    logging.warning(f"Failed to process image {src}: {e}")
                failed_count += 1
                # Remove the image if processing failed
                img.decompose()
        
        # Log processing statistics
        if verbose or processed_count > 0:
            compression_ratio = 0
            if total_original_size > 0:
                compression_ratio = (1 - total_optimized_size / total_original_size) * 100
            
            logging.info(
                f"Image processing complete: {processed_count} processed, {cached_count} cached, "
                f"{skipped_count} skipped, {failed_count} failed. "
                f"Compression: {total_original_size} -> {total_optimized_size} bytes "
                f"({compression_ratio:.1f}% reduction)"
            )
            
            # Log cache statistics
            cache_stats = self.image_cache.get_stats()
            logging.info(
                f"Cache status: {cache_stats['total_files']} files, "
                f"{cache_stats['total_size_mb']:.1f}MB "
                f"({cache_stats['usage_percentage']:.1f}% of limit)"
            )
        
        return str(soup)
    
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
        Generate a PDF from an issue's articles.
        
        Args:
            issue_id (str): UUID of the issue
            days_back (int): Number of days to look back for articles
            max_articles_per_publication (int): Maximum articles per publication
            layout_type (str): Layout type ('newspaper' or 'essay')
            output_filename (str, optional): Custom output filename
            keep_html (bool): Whether to keep the intermediate HTML file
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
                logging.info(f"Generating PDF for issue {issue_id}")
            
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
                                article['content'] = self.clean_html_content(content, verbose)
                                articles.append(article)
                        except Exception as e:
                            if verbose:
                                logging.warning(f"Failed to fetch content for {article['title']}: {e}")
            
            if not articles:
                result['error'] = "No article content could be fetched"
                return result
            
            # Generate HTML
            html_content = self.create_combined_html(
                articles=articles,
                issue_info=issue_info,
                layout_type=layout_type,
                verbose=verbose
            )
            
            # Process images
            html_content = self.download_and_cache_images(html_content, verbose)
            
            # Generate output filename
            if not output_filename:
                safe_title = "".join(c for c in issue_info['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = safe_title.replace(' ', '_')[:20]
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                output_filename = f"{safe_title}_{timestamp}"
            
            html_path = self.output_dir / f"{output_filename}.html"
            
            # Save HTML if requested
            if keep_html:
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                result['html_path'] = str(html_path)
            
            # Generate PDF
            if verbose:
                logging.info(f"Generating PDF: {output_filename}.pdf")
            
            if not HTML:
                result['error'] = "WeasyPrint not available. Install with: pip install weasyprint"
                return result
            
            html_obj = HTML(string=html_content, base_url=str(self.base_dir))
            
            # Generate PDF in memory and upload to Supabase storage
            pdf_bytes = html_obj.write_pdf()
            supabase_url = self.storage_service.upload_pdf(pdf_bytes, output_filename)
            
            result.update({
                'success': True,
                'pdf_url': supabase_url,
                'issue_info': issue_info,
                'articles_count': len(articles),
                'layout_type': layout_type
            })
            
            if verbose:
                logging.info(f"PDF uploaded successfully to Supabase: {supabase_url}")
            
        except Exception as e:
            result['error'] = f"PDF generation failed: {str(e)}"
            if verbose:
                logging.error(f"PDF generation error: {e}")
        
        return result
    
    def _fetch_article_content(self, url: str) -> Optional[str]:
        """
        Fetch the full content of an article from its URL.
        
        Args:
            url (str): Article URL
            
        Returns:
            str: Article content or None if failed
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
    
    def create_combined_html(
        self, 
        articles: List[Dict], 
        issue_info: Dict,
        layout_type: str = 'newspaper',
        verbose: bool = False
    ) -> str:
        """
        Create combined HTML content from multiple articles using CSS-based styling.
        
        Args:
            articles (list): List of article dictionaries
            issue_info (dict): Issue information
            layout_type (str): Layout type ('newspaper' or 'essay')
            verbose (bool): Enable verbose output
            
        Returns:
            str: Combined HTML content
        """
        if verbose:
            logging.info(f"Creating combined HTML with {len(articles)} articles in {layout_type} layout")
        
        # Generate HTML based on layout type
        if layout_type == 'newspaper':
            return self._create_newspaper_html(articles, issue_info, verbose)
        else:  # essay
            return self._create_essay_html(articles, issue_info, verbose)
    
    def _create_newspaper_html(self, articles: List[Dict], issue_info: Dict, verbose: bool = False) -> str:
        """Create newspaper-style HTML using Jinja2 template."""
        
        # Read CSS file
        css_path = self.styles_dir / "newspaper.css"
        css_content = ""
        if css_path.exists():
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
        elif verbose:
            logging.warning(f"CSS file not found: {css_path}")
        
        # Process articles content
        processed_articles = []
        for article in articles:
            processed_article = article.copy()
            content = article.get('content', '')
            
            # Clean and process content
            if content:
                content = self.clean_html_content(content, verbose=False)
                content = self.download_and_cache_images(content, verbose=verbose)
                processed_article['content'] = content
            
            processed_articles.append(processed_article)
        
        # Prepare template context
        context = {
            'issue_info': issue_info,
            'articles': processed_articles,
            'css_content': css_content,
            'current_date': datetime.now().strftime("%A, %B %d, %Y")
        }
        
        try:
            # Load and render template
            template = self.jinja_env.get_template('newspaper.html')
            return template.render(**context)
        except Exception as e:
            if verbose:
                logging.error(f"Template rendering failed: {e}")
            # Fallback to original method if template fails
            return self._create_fallback_html(processed_articles, issue_info, 'newspaper')
    
    def _create_essay_html(self, articles: List[Dict], issue_info: Dict, verbose: bool = False) -> str:
        """Create essay-style HTML using Jinja2 template."""
        
        # Read CSS file
        css_path = self.styles_dir / "essay.css"
        css_content = ""
        if css_path.exists():
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
        elif verbose:
            logging.warning(f"CSS file not found: {css_path}")
        
        # Process articles content
        processed_articles = []
        for article in articles:
            processed_article = article.copy()
            content = article.get('content', '')
            
            # Clean and process content
            if content:
                content = self.clean_html_content(content, verbose=False)
                content = self.download_and_cache_images(content, verbose=verbose)
                processed_article['content'] = content
            
            processed_articles.append(processed_article)
        
        # Prepare template context
        context = {
            'issue_info': issue_info,
            'articles': processed_articles,
            'css_content': css_content,
            'current_date': datetime.now().strftime("%B %d, %Y")
        }
        
        try:
            # Load and render template
            template = self.jinja_env.get_template('essay.html')
            return template.render(**context)
        except Exception as e:
            if verbose:
                logging.error(f"Template rendering failed: {e}")
            # Fallback to original method if template fails
            return self._create_fallback_html(processed_articles, issue_info, 'essay')
    
    def _create_fallback_html(
        self, 
        articles: List[Dict], 
        issue_info: Dict,
        layout_type: str
    ) -> str:
        """
        Create simple HTML content as fallback when CSS generation fails.
        
        Args:
            articles (list): List of article dictionaries
            issue_info (dict): Issue information
            layout_type (str): Layout type
            
        Returns:
            str: Simple HTML content
        """
        html_parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<meta charset="UTF-8">',
            f'<title>{issue_info.get("title", "Newsletter Digest")}</title>',
            '<style>',
            'body { font-family: Georgia, serif; margin: 40px; line-height: 1.6; }',
            '.article { margin-bottom: 40px; border-bottom: 1px solid #ccc; padding-bottom: 20px; }',
            '.article-title { font-size: 24px; font-weight: bold; margin-bottom: 10px; }',
            '.article-meta { color: #666; margin-bottom: 15px; }',
            '</style>',
            '</head>',
            '<body>',
            f'<h1>{issue_info.get("title", "Newsletter Digest")}</h1>',
            f'<p>Generated on {datetime.now().strftime("%B %d, %Y")}</p>'
        ]
        
        for i, article in enumerate(articles, 1):
            html_parts.extend([
                '<div class="article">',
                f'<h2 class="article-title">{article.get("title", f"Article {i}")}</h2>',
                f'<div class="article-meta">By {article.get("author", "Unknown")} | {article.get("date_published", "")}</div>',
                f'<div class="article-content">{article.get("content", "No content available")}</div>',
                '</div>'
            ])
        
        html_parts.extend(['</body>', '</html>'])
        
        return '\n'.join(html_parts)
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics"""
        return get_memory_stats()
    
    def force_memory_cleanup(self) -> Dict[str, Any]:
        """Force memory cleanup and garbage collection"""
        return memory_manager.force_garbage_collection("manual_pdf_service_cleanup")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service-specific statistics including memory and cache"""
        memory_stats = self.get_memory_stats()
        cache_stats = self.get_image_cache_stats()
        
        return {
            'memory': memory_stats,
            'image_cache': cache_stats,
            'settings': {
                'max_image_size_mb': memory_settings.MAX_IMAGE_SIZE_MB,
                'max_cache_size_mb': memory_settings.MAX_CACHE_SIZE_MB,
                'max_article_length': memory_settings.MAX_ARTICLE_LENGTH,
                'image_compression_enabled': memory_settings.ENABLE_IMAGE_COMPRESSION,
                'webp_conversion_enabled': memory_settings.ENABLE_WEBP_CONVERSION
            }
        }