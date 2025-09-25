from typing import List
import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin
from models import Article, Publication

class RSSService:

    def get_feed_url(self, webpage_url) -> str:
        """
        Discover RSS feed URL from a given webpage URL by checking HTML head for feed links.
        
        Args:
            webpage_url (str): URL of the webpage to check for RSS feeds
            
        Returns:
            str: The discovered RSS feed URL or None if not found
            
        Raises:
            requests.RequestException: If there's an error fetching the webpage
        """
        try:
            # Ensure the URL starts with http:// or https://
            if not webpage_url.startswith(('http://', 'https://')):
                webpage_url = 'https://' + webpage_url

            # Fetch the webpage content
            response = requests.get(webpage_url)
            response.raise_for_status()
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for RSS feed links in the HTML head
            # Common types of feed links to check for
            feed_types = [
                {'type': 'application/rss+xml'},
                {'type': 'application/atom+xml'},
                {'type': 'application/feed+json'},
                {'rel': 'alternate', 'type': 'application/rss+xml'},
                {'rel': 'alternate', 'type': 'application/atom+xml'}
            ]
            
            # Check for feed links in the head
            for feed_type in feed_types:
                feed_link = soup.find('link', attrs=feed_type)
                if feed_link and feed_link.get('href'):
                    # Make sure we have an absolute URL
                    feed_url = urljoin(webpage_url, feed_link['href'])
                    return feed_url
            
            # If no feed link found in head, try common feed URLs
            common_paths = ['/feed', '/rss', '/feed.xml', '/rss.xml', '/atom.xml']
            for path in common_paths:
                test_url = urljoin(webpage_url, path)
                try:
                    test_response = requests.get(test_url)
                    if test_response.status_code == 200 and 'xml' in test_response.headers.get('content-type', ''):
                        return test_url
                except requests.RequestException:
                    continue
            
            return None
            
        except requests.RequestException as e:
            logging.error(f"Error fetching webpage {webpage_url}: {str(e)}")
            raise

    def get_publication_metadata(self, feed_url) -> Publication:
        """Extract publication metadata from RSS feed."""
        pass

    def get_articles(
        self, 
        feed_url: str,
        skip: int = 0,
        limit: int = 10
    ) -> tuple[List[Article], int]:
        """
        Fetch and parse articles from an RSS feed with pagination.
        
        Args:
            feed_url: URL of the RSS feed
            skip: Number of articles to skip (for pagination)
            limit: Maximum number of articles to return
            
        Returns:
            tuple[List[Article], int]: Tuple containing:
                - List of parsed Article objects
                - Total number of articles available
            
        Raises:
            requests.RequestException: If there's an error fetching the feed
        """
        import xml.etree.ElementTree as ET
        from datetime import datetime
        import email.utils
        from uuid import uuid4
        
        articles = []
        
        try:
            # Fetch the RSS feed
            headers = {
                'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/91.0.4472.124 Safari/537.36')
            }
            response = requests.get(feed_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse XML content
            root = ET.fromstring(response.text)
            
            # Find the channel element (works for both RSS and Atom feeds)
            channel_elem = root.find('.//channel')
            channel = root if channel_elem is None else channel_elem
            
            # Process each item/entry
            items = []
            rss_items = channel.findall('.//item')
            atom_items = channel.findall('.//{http://www.w3.org/2005/Atom}entry')
            items = rss_items if rss_items else atom_items
            
            for item in items:
                # Extract article data with namespace handling
                ns = {'content': 'http://purl.org/rss/1.0/modules/content/',
                     'dc': 'http://purl.org/dc/elements/1.1/',
                     'atom': 'http://www.w3.org/2005/Atom'}
                
                # Get title (handle CDATA sections)
                title_elem = item.find('title')
                if title_elem is None:
                    title_elem = item.find('.//{http://www.w3.org/2005/Atom}title')
                title = "Untitled"
                if title_elem is not None:
                    # Handle possible CDATA content
                    title = ''.join(title_elem.itertext()).strip()
                
                # Get author (handle CDATA sections)
                author = "Unknown Author"
                author_elem = item.find('author')
                if author_elem is None:
                    author_elem = item.find('dc:creator', ns)
                if author_elem is None:
                    author_elem = item.find('.//{http://www.w3.org/2005/Atom}author//{http://www.w3.org/2005/Atom}name')
                if author_elem is not None:
                    author = ''.join(author_elem.itertext()).strip()
                
                # Get link/URL
                link_elem = item.find('link')
                if link_elem is None:
                    link_elem = item.find('.//{http://www.w3.org/2005/Atom}link[@rel="alternate"][@type="text/html"]')
                content_url = ''
                if link_elem is not None:
                    if link_elem.text:
                        content_url = link_elem.text.strip()
                    elif link_elem.get('href'):
                        content_url = link_elem.get('href').strip()
                
                # Get publication date
                date_published = None
                date_elem = item.find('pubDate')
                if date_elem is None:
                    date_elem = item.find('dc:date', ns)
                if date_elem is None:
                    date_elem = item.find('.//{http://www.w3.org/2005/Atom}published')
                if date_elem is None:
                    date_elem = item.find('.//{http://www.w3.org/2005/Atom}updated')
                
                if date_elem is not None and date_elem.text:
                    try:
                        # Try parsing as email format (RFC 2822)
                        date_tuple = email.utils.parsedate_tz(date_elem.text)
                        if date_tuple:
                            date_published = datetime(*date_tuple[:6])
                        else:
                            # Try ISO format
                            date_published = datetime.fromisoformat(date_elem.text.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        date_published = datetime.now(datetime.UTC)
                else:
                    date_published = datetime.now(datetime.UTC)
                
                # Create Article object
                article = Article(
                    id=uuid4(),
                    title=title[:255],  # Ensure we don't exceed max_length
                    subtitle=None,  # Could be extracted from description if needed
                    date_published=date_published,
                    author=author[:255],
                    content_url=content_url[:512],
                    publication_id=None,  # This would be set when saving to database
                    storage_url=None  # This would be set when content is stored
                )
                
                articles.append(article)
            
            total_articles = len(articles)
            
            # Apply pagination
            paginated_articles = articles[skip:skip + limit]
            
            return paginated_articles, total_articles
            
        except (requests.RequestException, ET.ParseError) as e:
            logging.error(f"Error processing RSS feed {feed_url}: {str(e)}")
            raise