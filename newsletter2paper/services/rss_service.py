from typing import List, Optional
import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta, timezone
import email.utils
import xml.etree.ElementTree as ET
from models import Article, Publication

from services.database_service import DatabaseService

DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/115.0.0.0 Safari/537.36'
    )
}

class RSSService:
    def __init__(self):
        """Initialize RSS service with database connection."""
        self.db = DatabaseService()

    def _is_feed_content_type(self, content_type: str) -> bool:
        """Check if content-type indicates a feed."""
        if not content_type:
            return False
        ct = content_type.lower()
        return any(x in ct for x in ('application/rss+xml', 'application/atom+xml', 'xml', 'text/xml'))

    def _guess_common_feed_paths(self, parsed_url):
        """Generate common feed paths to try relative to the site root."""
        base = f"{parsed_url.scheme}://{parsed_url.netloc}"
        return [
            urljoin(base, p) for p in (
                '/feed', '/rss', '/rss.xml', '/atom.xml', '/feeds/posts/default',
                '/feeds', '/feed.xml', '/index.xml'
            )
        ]

    def get_feed_url(self, webpage_url: str, timeout: int = 10, verbose: bool = False) -> Optional[str]:
        """
        Discover RSS feed URL from a given webpage URL using comprehensive discovery.
        
        Strategy:
        - HEAD request to see content-type; if it looks like XML/feed, return the URL
        - GET the HTML page and parse <link rel="alternate"> tags with feed mime types
        - Try common feed paths on the site root
        - Return the first reachable URL that looks like a feed
        
        Args:
            webpage_url (str): URL of the webpage to check for RSS feeds
            timeout (int): Request timeout in seconds
            verbose (bool): Enable verbose logging
            
        Returns:
            str: The discovered RSS feed URL or None if not found
            
        Raises:
            requests.RequestException: If there's an error fetching the webpage
        """
        try:
            # Ensure the URL starts with http:// or https://
            if not webpage_url.startswith(('http://', 'https://')):
                webpage_url = 'https://' + webpage_url

            # Fast HEAD to detect direct feed URLs
            if verbose:
                logging.info(f"HEAD {webpage_url}")
            try:
                head = requests.head(webpage_url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
                ct = head.headers.get('content-type', '')
                if verbose:
                    logging.info(f"  content-type: {ct}")
                if self._is_feed_content_type(ct):
                    return head.url
            except requests.RequestException:
                # HEAD may be blocked on some sites; we'll try GET below
                if verbose:
                    logging.info("  HEAD failed, falling back to GET")

            # GET the URL and parse HTML for <link rel=alternate> tags
            if verbose:
                logging.info(f"GET {webpage_url}")
            response = requests.get(webpage_url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            # If the fetched URL itself is a feed by content-type, return it
            ct = response.headers.get('content-type', '')
            if self._is_feed_content_type(ct):
                if verbose:
                    logging.info(f"  page returned feed-like content-type: {ct}")
                return response.url

            content = response.text
            soup = BeautifulSoup(content, 'html.parser')

            # Look for <link rel="alternate" type="application/rss+xml" href="...">
            link_tags = soup.find_all('link', rel=lambda x: x and 'alternate' in x.lower())

            candidates = []
            for tag in link_tags:
                t = (tag.get('type') or '').lower()
                href = tag.get('href')
                if not href:
                    continue
                full = urljoin(response.url, href)
                if t and any(x in t for x in ('rss', 'atom', 'xml')):
                    candidates.append(full)

            # Also consider <a> tags that mention 'rss' or 'feed' in href or text
            if not candidates:
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    text = (a.get_text() or '').lower()
                    if 'rss' in href.lower() or 'feed' in href.lower() or 'atom' in href.lower() or 'rss' in text or 'feed' in text:
                        candidates.append(urljoin(response.url, href))

            # Deduplicate while preserving order
            seen = set()
            candidates = [x for x in candidates if not (x in seen or seen.add(x))]

            # Validate candidate URLs by issuing a HEAD/GET and checking content-type or XML root
            for cand in candidates:
                try:
                    if verbose:
                        logging.info(f"Checking candidate: {cand}")
                    # Try HEAD first
                    try:
                        h = requests.head(cand, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
                        cand_ct = h.headers.get('content-type', '')
                        if self._is_feed_content_type(cand_ct):
                            return h.url
                    except requests.RequestException:
                        pass

                    # GET and check for XML root
                    r = requests.get(cand, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
                    r.raise_for_status()
                    ct = r.headers.get('content-type', '')
                    if self._is_feed_content_type(ct):
                        return r.url
                    # Quick heuristic: starts with <?xml or <rss or <feed
                    txt = (r.text or '').lstrip()[:200].lower()
                    if txt.startswith('<?xml') or txt.startswith('<rss') or txt.startswith('<feed'):
                        return r.url
                except requests.RequestException:
                    if verbose:
                        logging.info(f"  candidate failed: {cand}")
                    continue

            # If still not found, try common feed paths at site root
            parsed = urlparse(response.url)
            for path in self._guess_common_feed_paths(parsed):
                try:
                    if verbose:
                        logging.info(f"Trying common path: {path}")
                    r = requests.head(path, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
                    ct = r.headers.get('content-type', '')
                    if self._is_feed_content_type(ct):
                        return r.url
                    # Fallback to GET
                    r = requests.get(path, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
                    r.raise_for_status()
                    ct = r.headers.get('content-type', '')
                    if self._is_feed_content_type(ct):
                        return r.url
                    txt = (r.text or '').lstrip()[:200].lower()
                    if txt.startswith('<?xml') or txt.startswith('<rss') or txt.startswith('<feed'):
                        return r.url
                except requests.RequestException:
                    continue

            if verbose:
                logging.info("No feed discovered")
            return None

        except requests.RequestException as e:
            logging.error(f"Error fetching webpage {webpage_url}: {str(e)}")
            raise

    def validate_rss_content(self, xml_content: str, verbose: bool = False) -> bool:
        """
        Validate that the fetched content is valid RSS/XML.
        
        Args:
            xml_content (str): XML content to validate
            verbose (bool): Enable verbose output
            
        Returns:
            bool: True if valid RSS content
        """
        try:
            root = ET.fromstring(xml_content)
            
            # Check if it's an RSS feed
            if root.tag.lower() == 'rss' or root.tag.endswith('}rss'):
                if verbose:
                    logging.info("Valid RSS feed detected")
                return True
            
            # Check if it's an Atom feed
            if root.tag.endswith('}feed') or (root.tag.lower() == 'feed'):
                # Check for Atom namespace or just 'feed' tag
                if verbose:
                    logging.info("Atom feed detected (may need conversion)")
                return True
            
            # Check for channel element (RSS indicator)
            if root.find('.//channel') is not None:
                if verbose:
                    logging.info("RSS channel found")
                return True
            
            if verbose:
                logging.info(f"Unknown feed format. Root tag: {root.tag}")
            return False
            
        except ET.ParseError as e:
            if verbose:
                logging.info(f"XML parsing error: {e}")
            return False

    def extract_feed_info(self, xml_content: str, verbose: bool = False) -> dict:
        """
        Extract basic information from the RSS feed.
        
        Args:
            xml_content (str): RSS XML content
            verbose (bool): Enable verbose output
            
        Returns:
            dict: Feed information (title, description, etc.)
        """
        info = {
            'title': 'unknown_feed',
            'description': '',
            'link': '',
            'item_count': 0
        }
        
        try:
            root = ET.fromstring(xml_content)
            
            # Find channel element
            channel = root.find('.//channel')
            if channel is not None:
                title_elem = channel.find('title')
                if title_elem is not None:
                    info['title'] = title_elem.text or 'unknown_feed'
                
                desc_elem = channel.find('description')
                if desc_elem is not None:
                    info['description'] = desc_elem.text or ''
                
                link_elem = channel.find('link')
                if link_elem is not None:
                    info['link'] = link_elem.text or ''
                
                # Count items
                items = channel.findall('item')
                info['item_count'] = len(items)
            
            if verbose:
                logging.info(f"Feed info: {info['title']} ({info['item_count']} items)")
            
        except ET.ParseError:
            if verbose:
                logging.info("Could not parse feed info")
        
        return info

    def parse_rss_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse RSS date string to datetime object.
        
        Args:
            date_str (str): Date string from RSS feed
            
        Returns:
            datetime or None: Parsed datetime object
        """
        if not date_str:
            return None
        
        try:
            # Try parsing as email format (RFC 2822)
            return datetime(*email.utils.parsedate(date_str)[:6])
        except (TypeError, ValueError):
            pass
        
        # Try common ISO formats
        for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']:
            try:
                return datetime.strptime(date_str.replace('Z', '+0000'), fmt)
            except ValueError:
                continue
        
        return None

    def filter_articles_by_date(self, articles: List[dict], start_date: Optional[datetime] = None, 
                              end_date: Optional[datetime] = None, verbose: bool = False) -> List[dict]:
        """
        Filter articles by date range.
        
        Args:
            articles (list): List of article dictionaries
            start_date (datetime, optional): Start of date range
            end_date (datetime, optional): End of date range
            verbose (bool): Enable verbose output
            
        Returns:
            list: Filtered articles
        """
        if not start_date and not end_date:
            return articles
        
        filtered = []
        for article in articles:
            article_date = self.parse_rss_date(article.get('pub_date'))
            
            if not article_date:
                if verbose:
                    logging.info(f"  - Skipping article with unparseable date: {article.get('title', 'Unknown')}")
                continue
            
            # Convert to naive datetime for comparison
            if article_date.tzinfo:
                article_date = article_date.replace(tzinfo=None)
            
            if start_date and article_date < start_date:
                continue
            if end_date and article_date > end_date:
                continue
            
            filtered.append(article)
        
        if verbose:
            logging.info(f"  - Filtered {len(articles)} articles to {len(filtered)} within date range")
        
        return filtered

    def get_date_range_for_period(self, period: str) -> tuple[datetime, datetime]:
        """
        Get start and end dates for a given period.
        
        Args:
            period (str): Period string ('last-week', 'last-month', or date range)
            
        Returns:
            tuple: (start_date, end_date) as datetime objects
        """
        now = datetime.now()
        
        if period == 'last-week':
            start_date = now - timedelta(days=7)
            return start_date, now
        elif period == 'last-month':
            start_date = now - timedelta(days=30)
            return start_date, now
        elif ',' in period:
            # Custom date range: "2025-01-01,2025-01-31"
            try:
                start_str, end_str = period.split(',', 1)
                start_date = datetime.strptime(start_str.strip(), '%Y-%m-%d')
                end_date = datetime.strptime(end_str.strip(), '%Y-%m-%d')
                return start_date, end_date
            except ValueError:
                raise ValueError(f"Invalid date range format: {period}. Use YYYY-MM-DD,YYYY-MM-DD")
        else:
            raise ValueError(f"Unknown period: {period}")

    def fetch_rss_feed_content(self, rss_url: str, verbose: bool = False) -> str:
        """
        Fetch RSS feed content from a URL with validation.
        
        Args:
            rss_url (str): URL of the RSS feed
            verbose (bool): Enable verbose output
            
        Returns:
            str: RSS feed XML content
            
        Raises:
            requests.RequestException: If fetching fails
            ValueError: If content is not valid RSS
        """
        if verbose:
            logging.info(f"Fetching RSS feed from: {rss_url}")
        
        try:
            response = requests.get(rss_url, headers=DEFAULT_HEADERS, timeout=30)
            response.raise_for_status()
            
            if verbose:
                logging.info(f"Successfully fetched {len(response.content)} bytes")
            
            # Validate the content
            if not self.validate_rss_content(response.text, verbose):
                raise ValueError("Fetched content is not a valid RSS feed")
            
            return response.text
            
        except requests.RequestException as e:
            raise requests.RequestException(f"Failed to fetch RSS feed: {e}")

    async def get_articles(
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
            # Fetch the RSS feed using the new method
            xml_content = self.fetch_rss_feed_content(feed_url, verbose=False)
            
            # Parse XML content
            root = ET.fromstring(xml_content)
            
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
                    # Handle possible CDATA content using itertext to get all text nodes
                    title = ''.join(title_elem.itertext()).strip()

                # Get description/subtitle with better content extraction
                subtitle = None
                # Try multiple content sources in order of preference
                content_sources = [
                    'description',
                    'summary', 
                    './/{http://purl.org/rss/1.0/modules/content/}encoded',
                    './/{http://www.w3.org/2005/Atom}summary',
                    './/{http://www.w3.org/2005/Atom}content'
                ]
                
                for source in content_sources:
                    description_elem = item.find(source)
                    if description_elem is not None and description_elem.text:
                        # Handle possible CDATA content and strip HTML tags if needed
                        subtitle = ''.join(description_elem.itertext()).strip()
                        if subtitle:
                            # Truncate to fit the max_length of 255 characters
                            subtitle = subtitle[:255]
                            break
                
                # Get author (handle CDATA sections and multiple author formats)
                author = "Unknown Author"
                author_sources = [
                    'author',
                    'dc:creator',
                    './/{http://www.w3.org/2005/Atom}author//{http://www.w3.org/2005/Atom}name'
                ]
                
                for source in author_sources:
                    if source.startswith('dc:'):
                        author_elem = item.find(source, ns)
                    else:
                        author_elem = item.find(source)
                    
                    if author_elem is not None:
                        author_text = ''.join(author_elem.itertext()).strip()
                        if author_text:
                            author = author_text
                            break
                
                # Get link/URL with better handling
                content_url = ''
                link_elem = item.find('link')
                if link_elem is None:
                    # Try Atom-style links
                    link_elem = item.find('.//{http://www.w3.org/2005/Atom}link[@rel="alternate"][@type="text/html"]')
                    if link_elem is None:
                        # Try any Atom link
                        link_elem = item.find('.//{http://www.w3.org/2005/Atom}link')
                
                if link_elem is not None:
                    if link_elem.text and link_elem.text.strip():
                        content_url = link_elem.text.strip()
                    elif link_elem.get('href'):
                        content_url = link_elem.get('href').strip()
                
                # Get publication date with enhanced parsing
                date_published = None
                date_sources = [
                    'pubDate',
                    'dc:date',
                    './/{http://www.w3.org/2005/Atom}published',
                    './/{http://www.w3.org/2005/Atom}updated'
                ]
                
                for source in date_sources:
                    if source.startswith('dc:'):
                        date_elem = item.find(source, ns)
                    else:
                        date_elem = item.find(source)
                    
                    if date_elem is not None and date_elem.text:
                        parsed_date = self.parse_rss_date(date_elem.text)
                        if parsed_date:
                            date_published = parsed_date
                            break
                
                # Fallback to current time if no date found
                if not date_published:
                    date_published = datetime.now(timezone.utc)
                
                # Ensure timezone awareness
                if date_published.tzinfo is None:
                    date_published = date_published.replace(tzinfo=timezone.utc)
                
                # Create Article object
                article = Article(
                    id=uuid4(),
                    title=title[:255],  # Ensure we don't exceed max_length
                    subtitle=subtitle,  # Set from extracted description
                    date_published=date_published,
                    author=author[:255],
                    content_url=content_url[:512],
                    publication_id=None,  # This would be set when saving to database
                    storage_url=None  # This would be set when content is stored
                )
                
                articles.append(article)
            
            # Look up publication by feed URL
            publication = await self.db.get_publication_by_url(feed_url)
            if publication:
                # Update all articles with the publication ID
                for article in articles:
                    article.publication_id = publication['id']

            total_articles = len(articles)
            
            # Apply pagination
            paginated_articles = articles[skip:skip + limit]
            
            return paginated_articles, total_articles
            
        except (requests.RequestException, ET.ParseError) as e:
            logging.error(f"Error processing RSS feed {feed_url}: {str(e)}")
            raise
    
    async def fetch_recent_articles_for_issue(
        self, 
        issue_id: str, 
        days_back: int = 7,
        max_articles_per_publication: int = 5
    ) -> dict:
        """
        Fetch recent articles for all publications in an issue.
        
        Args:
            issue_id: UUID of the issue
            days_back: Number of days to look back for articles
            max_articles_per_publication: Maximum articles per publication
            
        Returns:
            Dictionary with issue info and articles grouped by publication
        """
        try:
            # Get issue details
            issue_result = self.db.client.table('issues')\
                .select('*')\
                .eq('id', issue_id)\
                .execute()
            
            if not issue_result.data:
                raise ValueError(f"Issue not found: {issue_id}")
            
            issue = issue_result.data[0]
            
            # Get publications for this issue
            publications_result = self.db.client.table('issue_publications')\
                .select('*, publications(*)')\
                .eq('issue_id', issue_id)\
                .execute()
            
            if not publications_result.data:
                return {
                    'issue': issue,
                    'publications': [],
                    'articles_by_publication': {},
                    'total_articles': 0
                }
            
            # Extract publications with their remove_images settings from junction table
            publications = []
            publication_settings = {}  # Map pub_id -> remove_images setting
            for item in publications_result.data:
                if item['publications']:
                    pub = item['publications']
                    pub_id = pub['id']
                    # Store the remove_images setting from the junction table
                    publication_settings[pub_id] = item.get('remove_images', False)
                    publications.append(pub)
            
            # Calculate cutoff date
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            articles_by_publication = {}
            total_articles = 0
            
            for publication in publications:
                pub_id = publication['id']
                rss_url = publication.get('rss_feed_url')
                
                if not rss_url:
                    logging.warning(f"No RSS URL for publication {publication.get('title', pub_id)}")
                    articles_by_publication[pub_id] = []
                    continue
                
                try:
                    # Fetch articles using the existing method
                    articles, _ = await self.get_articles(rss_url, skip=0, limit=max_articles_per_publication * 2)
                    
                    # Filter articles by date
                    recent_articles = []
                    for article in articles:
                        if article.date_published and article.date_published >= cutoff_date:
                            # Convert Article object to dictionary for easier handling
                            article_dict = {
                                'id': str(article.id),
                                'title': article.title,
                                'subtitle': article.subtitle,
                                'author': article.author,
                                'content_url': article.content_url,
                                'date_published': article.date_published.isoformat(),
                                'publication_id': pub_id,
                                'publication_title': publication.get('title', ''),
                                'publication_publisher': publication.get('publisher', ''),
                                'remove_images': publication_settings.get(pub_id, False)  # Per-publication setting
                            }
                            recent_articles.append(article_dict)
                            
                            if len(recent_articles) >= max_articles_per_publication:
                                break
                    
                    articles_by_publication[pub_id] = recent_articles
                    total_articles += len(recent_articles)
                    
                    logging.info(f"Found {len(recent_articles)} recent articles for {publication.get('title', pub_id)}")
                    
                except Exception as e:
                    logging.error(f"Error fetching articles for publication {publication.get('title', pub_id)}: {str(e)}")
                    articles_by_publication[pub_id] = []
            
            return {
                'issue': issue,
                'publications': publications,
                'articles_by_publication': articles_by_publication,
                'total_articles': total_articles,
                'date_range': {
                    'from': cutoff_date.isoformat(),
                    'to': datetime.now(timezone.utc).isoformat(),
                    'days_back': days_back
                }
            }
            
        except Exception as e:
            logging.error(f"Error fetching articles for issue {issue_id}: {str(e)}")
            raise

    async def fetch_articles_from_feeds(self, feed_urls: List[str], start_date: Optional[datetime] = None, 
                                      end_date: Optional[datetime] = None, verbose: bool = False) -> List[dict]:
        """
        Fetch articles from multiple RSS feeds.
        
        Args:
            feed_urls (List[str]): List of RSS feed URLs
            start_date (datetime, optional): Start of date range
            end_date (datetime, optional): End of date range
            verbose (bool): Enable verbose output
            
        Returns:
            List[dict]: List of all articles from all feeds
        """
        all_articles = []
        failed_feeds = []
        
        if verbose:
            logging.info(f"Processing {len(feed_urls)} feeds")
        
        for i, feed_url in enumerate(feed_urls, 1):
            if verbose:
                logging.info(f"[{i}/{len(feed_urls)}] Processing: {feed_url}")
            
            try:
                # Fetch articles using the existing method
                articles, _ = await self.get_articles(feed_url, skip=0, limit=100)
                
                # Convert Article objects to dictionaries and add feed info
                for article in articles:
                    article_dict = {
                        'id': str(article.id),
                        'title': article.title,
                        'subtitle': article.subtitle,
                        'author': article.author,
                        'content_url': article.content_url,
                        'date_published': article.date_published.isoformat() if article.date_published else None,
                        'publication_id': str(article.publication_id) if article.publication_id else None,
                        'feed_url': feed_url,
                        'pub_date': article.date_published.strftime('%a, %d %b %Y %H:%M:%S %z') if article.date_published else ''
                    }
                    all_articles.append(article_dict)
                
                if verbose:
                    logging.info(f"  ✅ Added {len(articles)} articles")
                
            except Exception as e:
                failed_feeds.append({'url': feed_url, 'error': str(e)})
                if verbose:
                    logging.error(f"  ❌ Failed: {e}")
        
        # Filter by date if specified
        if start_date or end_date:
            all_articles = self.filter_articles_by_date(all_articles, start_date, end_date, verbose)
        
        # Sort articles by date (newest first)
        all_articles.sort(
            key=lambda x: self.parse_rss_date(x.get('pub_date')) or datetime.min, 
            reverse=True
        )
        
        if verbose:
            logging.info(f"📊 Summary:")
            logging.info(f"  - Total articles: {len(all_articles)}")
            logging.info(f"  - Successful feeds: {len(feed_urls) - len(failed_feeds)}")
            logging.info(f"  - Failed feeds: {len(failed_feeds)}")
            if failed_feeds:
                logging.info("  - Failed URLs:")
                for failed in failed_feeds:
                    logging.info(f"    • {failed['url']}: {failed['error']}")
        
        return all_articles