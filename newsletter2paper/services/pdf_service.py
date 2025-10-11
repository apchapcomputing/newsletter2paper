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
from typing import Dict, List, Optional, Any

from services.rss_service import RSSService
from services.storage_service import StorageService

logger = logging.getLogger(__name__)

class PDFService:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.images_dir = self.base_dir / "images"
        self.styles_dir = self.base_dir / "styles"
        self.newspapers_dir = self.base_dir / "newspapers"
        self.output_dir = self.newspapers_dir  # Use newspapers dir as output directory
        
        self.rss_service = RSSService()
        self.storage_service = StorageService()
        
        # Ensure directories exist
        self.images_dir.mkdir(exist_ok=True)
        self.newspapers_dir.mkdir(exist_ok=True)
    
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
        
        if verbose:
            logging.info(f"Cleaned HTML: {widgets_removed} widgets, {forms_removed} forms, "
                        f"{inputs_removed} inputs, {subscription_elements_removed} subscription elements, "
                        f"{image_icons_removed} image icons removed")
        
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
    
    def download_and_cache_images(self, html_content: str, verbose: bool = False) -> str:
        """
        Download images from HTML content and replace URLs with local file paths.
        
        Args:
            html_content (str): HTML content containing image URLs
            verbose (bool): Enable verbose output
            
        Returns:
            str: Modified HTML content with local image paths
        """
        if verbose:
            logging.info("Processing images in HTML content...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')
        
        if not images:
            if verbose:
                logging.info("No images found in content")
            return str(soup)
        
        downloaded_count = 0
        failed_count = 0
        
        for img in images:
            src = img.get('src')
            if not src or src.startswith('data:') or src.startswith('file:'):
                continue
            
            try:
                # Create a hash of the URL for the filename
                url_hash = hashlib.md5(src.encode()).hexdigest()
                
                # Try to get file extension from URL
                extension = '.png'
                if '.' in src.split('/')[-1]:
                    extension = '.' + src.split('.')[-1].split('?')[0]
                
                local_filename = f"{url_hash}{extension}"
                local_path = self.images_dir / local_filename
                
                # Download if not already cached
                if not local_path.exists():
                    if verbose:
                        logging.info(f"Downloading image: {src}")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    
                    response = requests.get(src, headers=headers, timeout=10)
                    response.raise_for_status()
                    
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                
                # Update the img src to local path
                img['src'] = str(local_path)
                downloaded_count += 1
                
            except Exception as e:
                if verbose:
                    logging.warning(f"Failed to download image {src}: {e}")
                failed_count += 1
                # Remove the image if download failed
                img.decompose()
        
        if verbose:
            logging.info(f"Image processing complete: {downloaded_count} downloaded/cached, {failed_count} failed")
        
        return str(soup)
    
    async def generate_pdf_from_issue(
        self, 
        issue_id: str, 
        days_back: int = 7,
        max_articles_per_publication: int = 5,
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
            layout_type = issue_info.get('format', 'newspaper')
            
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
                'articles_count': len(articles)
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
        """Create newspaper-style HTML with embedded CSS."""
        
        # Read CSS file
        css_path = self.styles_dir / "newspaper.css"
        css_content = ""
        if css_path.exists():
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
        elif verbose:
            logging.warning(f"CSS file not found: {css_path}")
        
        # Build HTML
        html_parts = []
        html_parts.append(f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{issue_info.get('title', 'Newsletter Digest')}</title>
    <style>
{css_content}
    </style>
</head>
<body>''')
        
        # Add masthead
        date_str = datetime.now().strftime("%A, %B %d, %Y")
        total_articles = len(articles)
        
        html_parts.append(f'''
    <div class="masthead">
        <h1>{issue_info.get('title', 'THE NEWSLETTER DIGEST')}</h1>
        <div class="subtitle">Your Collection of Insights and Analysis</div>
        <div class="date">{date_str} • {total_articles} Articles</div>
    </div>''')
        
        # Start main content
        html_parts.append('<div class="newspaper-content">')
        
        # Add table of contents for multiple articles
        if len(articles) > 1:
            html_parts.append('<div class="newspaper-toc">')
            html_parts.append('<h3>IN THIS EDITION</h3>')
            html_parts.append('<ul>')
            
            for i, article in enumerate(articles, 1):
                title = article.get('title', f'Article {i}')
                publication = article.get('publication_name', article.get('feed_title', ''))
                
                html_parts.append('<li>')
                html_parts.append(f'<span class="toc-title">{title}</span>')
                if publication:
                    html_parts.append(f'<span class="toc-source"> - {publication}</span>')
                html_parts.append('</li>')
            
            html_parts.append('</ul>')
            html_parts.append('</div>')
        
        # Add articles
        for i, article in enumerate(articles, 1):
            title = article.get('title', f'Article {i}')
            author = article.get('author', '')
            publication = article.get('publication_name', article.get('feed_title', ''))
            content = article.get('content', '')
            
            # Clean and process content
            if content:
                content = self.clean_html_content(content, verbose=False)
                content = self.download_and_cache_images(content, verbose=verbose)
            
            # Create byline
            byline_parts = []
            if author:
                byline_parts.append(f"By {author}")
            if publication:
                if author:
                    byline_parts.append(f"({publication})")
                else:
                    byline_parts.append(f"From {publication}")
            
            byline = " ".join(byline_parts) if byline_parts else ""
            
            # Add article break for articles after the first
            article_class = "article-break" if i > 1 else ""
            
            html_parts.append(f'<div class="article {article_class}" id="article-{i}">')
            html_parts.append(f'<div class="headline">{title}</div>')
            if byline:
                html_parts.append(f'<div class="byline">{byline}</div>')
            html_parts.append(f'<div class="article-content">{content}</div>')
            html_parts.append('</div>')
            
            # Add separator between articles (except the last one)
            if i < len(articles):
                html_parts.append('<div class="article-separator">• • •</div>')
        
        # Close main content and HTML
        html_parts.append('</div>')  # Close newspaper-content
        html_parts.append('</body>')
        html_parts.append('</html>')
        
        return '\n'.join(html_parts)
    
    def _create_essay_html(self, articles: List[Dict], issue_info: Dict, verbose: bool = False) -> str:
        """Create essay-style HTML with embedded CSS."""
        
        # Read CSS file
        css_path = self.styles_dir / "essay.css"
        css_content = ""
        if css_path.exists():
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
        elif verbose:
            logging.warning(f"CSS file not found: {css_path}")
        
        # Build HTML
        html_parts = []
        html_parts.append(f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{issue_info.get('title', 'Newsletter Collection')}</title>
    <style>
{css_content}
    </style>
</head>
<body>''')
        
        # Add header for collection
        html_parts.append(f'''
    <div class="collection-header">
        <h1>{issue_info.get('title', 'Newsletter Collection')}</h1>
        <div class="collection-date">{datetime.now().strftime("%B %d, %Y")}</div>
        <div class="collection-summary">{len(articles)} articles compiled</div>
    </div>''')
        
        # Add table of contents for multiple articles
        if len(articles) > 1:
            html_parts.append('<div class="toc">')
            html_parts.append('<h2>Table of Contents</h2>')
            html_parts.append('<ul>')
            
            for i, article in enumerate(articles, 1):
                title = article.get('title', f'Article {i}')
                author = article.get('author', '')
                publication = article.get('publication_name', article.get('feed_title', ''))
                
                html_parts.append(f'<li>{i}. <a href="#article-{i}">{title}</a>')
                if author:
                    html_parts.append(f' <span class="toc-author">by {author}</span>')
                if publication:
                    html_parts.append(f' <span class="toc-publication">({publication})</span>')
                html_parts.append('</li>')
            
            html_parts.append('</ul>')
            html_parts.append('</div>')
        
        # Add articles
        for i, article in enumerate(articles, 1):
            title = article.get('title', f'Article {i}')
            author = article.get('author', '')
            publication = article.get('publication_name', article.get('feed_title', ''))
            pub_date = article.get('pub_date', article.get('published_date', ''))
            url = article.get('url', article.get('link', ''))
            content = article.get('content', '')
            
            # Clean and process content
            if content:
                content = self.clean_html_content(content, verbose=False)
                content = self.download_and_cache_images(content, verbose=verbose)
            
            html_parts.append(f'<div class="article" id="article-{i}">')
            
            # Article header
            html_parts.append('<div class="article-header">')
            html_parts.append(f'<div class="article-title">{title}</div>')
            
            if author:
                html_parts.append(f'<div class="article-meta">Author: {author}</div>')
            
            if pub_date:
                html_parts.append(f'<div class="article-meta">Published: {pub_date}</div>')
            
            if publication:
                html_parts.append(f'<div class="article-meta">Source: {publication}</div>')
            
            if url:
                html_parts.append(f'<div class="article-meta">URL: <a href="{url}">{url}</a></div>')
            
            html_parts.append('</div>')  # Close article-header
            
            # Article content
            html_parts.append('<div class="article-content">')
            html_parts.append(content)
            html_parts.append('</div>')
            
            html_parts.append('</div>')  # Close article
        
        # Close HTML
        html_parts.append('</body>')
        html_parts.append('</html>')
        
        return '\n'.join(html_parts)
    
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