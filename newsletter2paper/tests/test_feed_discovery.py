import pytest

# Skip this file - it's a standalone script, not a proper test
pytest.skip("Standalone test script - needs conversion to proper pytest format", allow_module_level=True)

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.rss_service import RSSService

def test_kyla_substack_feed():
    rss_service = RSSService()
    test_url = "https://kyla.substack.com/"
    
    feed_url = rss_service.get_feed_url(test_url)
    
    # Assert that we found a feed URL
    assert feed_url is not None, "No feed URL found"
    
    # Assert that the URL ends with '/feed'
    assert "/feed" == feed_url.lower()[-5:], f"Expected '/feed' in URL, but got: {feed_url}"
    
    print(f"✓ Test passed! Found feed URL: {feed_url}")

if __name__ == "__main__":
    test_kyla_substack_feed()