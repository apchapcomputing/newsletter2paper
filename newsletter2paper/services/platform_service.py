"""
Platform detection service for identifying publishing platforms (Substack, Ghost, Beehiiv, etc.)
from a URL or the page's HTML content.
"""

import re
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PLATFORM_SUBSTACK = "substack"
PLATFORM_GHOST = "ghost"
PLATFORM_BEEHIIV = "beehiiv"
PLATFORM_GENERIC = "generic"

DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/115.0.0.0 Safari/537.36'
    )
}

_URL_RULES = [
    (PLATFORM_SUBSTACK, re.compile(r'substack\.com', re.I)),
    (PLATFORM_BEEHIIV, re.compile(r'beehiiv\.com', re.I)),
    (PLATFORM_GHOST, re.compile(r'ghost\.io', re.I)),
]


class PlatformService:
    """Detects the publishing platform for a given URL."""

    def detect_from_url(self, url: str) -> Optional[str]:
        """Return platform name if URL matches a known pattern, else None."""
        for platform, pattern in _URL_RULES:
            if pattern.search(url):
                return platform
        return None

    def detect_from_html(self, url: str, timeout: int = 10) -> str:
        """Fetch the page and fingerprint the platform from meta tags and DOM patterns."""
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

            generator = ""
            gen_tag = soup.find('meta', attrs={'name': 'generator'})
            if gen_tag and gen_tag.get('content'):
                generator = gen_tag['content'].lower()

            if 'substack' in generator or soup.select_one('div.available-content'):
                return PLATFORM_SUBSTACK
            if 'ghost' in generator or soup.select_one('.gh-content'):
                return PLATFORM_GHOST
            if 'beehiiv' in generator or soup.select_one('.email-body-content'):
                return PLATFORM_BEEHIIV

        except Exception as e:
            logger.debug(f"HTML platform detection failed for {url}: {e}")

        return PLATFORM_GENERIC

    def detect(self, url: str, fetch_html_on_miss: bool = False) -> str:
        """
        Detect platform: URL pattern check first, HTML fetch as optional fallback.

        Args:
            url: The article or publication URL.
            fetch_html_on_miss: If True, fetch the page when URL patterns don't match.
                                Use only for one-off articles and first-time pub registration.
        """
        result = self.detect_from_url(url)
        if result:
            return result
        if fetch_html_on_miss:
            return self.detect_from_html(url)
        return PLATFORM_GENERIC
