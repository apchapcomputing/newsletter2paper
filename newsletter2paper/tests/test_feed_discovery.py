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