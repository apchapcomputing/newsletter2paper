import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin
from models import Publication

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

    def get_articles(self, feed_url):
        """Get articles from RSS feed."""
        pass