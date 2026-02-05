import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.publication import Publication


@pytest.fixture
def sample_publication():
    """Create a sample publication with required fields."""
    return Publication(
        title="Test Publication",
        url="https://example.com",
        rss_feed_url="https://example.com/feed",
        publisher="Test Publisher"
    )


def test_publication_creation(sample_publication):
    """Test that a publication can be created with required fields."""
    assert sample_publication.title == "Test Publication"
    assert sample_publication.url == "https://example.com"
    assert sample_publication.rss_feed_url == "https://example.com/feed"
    assert sample_publication.publisher == "Test Publisher"


def test_publication_url_fields():
    """Test publication URL fields."""
    pub = Publication(
        title="Substack Newsletter",
        url="https://kyla.substack.com",
        rss_feed_url="https://kyla.substack.com/feed",
        publisher="Kyla Scanlon"
    )
    assert pub.url.startswith("https://")
    assert pub.rss_feed_url.endswith("/feed")


def test_publication_string_representation(sample_publication):
    """Test string representation of publication."""
    str_repr = str(sample_publication)
    assert "Test Publication" in str_repr