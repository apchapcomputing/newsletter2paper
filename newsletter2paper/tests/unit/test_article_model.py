import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.article import Article

@pytest.fixture
def sample_article():
    """Create a sample article with all required fields."""
    return Article(
        title="Sample Title",
        author="Sample Author",
        date_published=datetime.now(),
        content_url="https://example.com/article"
    )

def test_article_creation(sample_article):
    """Test that an article can be created with required fields."""
    assert sample_article.title == "Sample Title"
    assert sample_article.author == "Sample Author"
    assert sample_article.content_url == "https://example.com/article"

def test_article_with_optional_fields():
    """Test article with optional fields."""
    article = Article(
        title="Test Article",
        author="Test Author",
        date_published=datetime.now(),
        content_url="https://example.com/test",
        subtitle="Test Subtitle",
        storage_url="https://storage.example.com/test.pdf"
    )
    assert article.subtitle == "Test Subtitle"
    assert article.storage_url == "https://storage.example.com/test.pdf"

def test_article_str_representation(sample_article):
    """Test string representation of article."""
    str_repr = str(sample_article)
    assert "Sample Title" in str_repr
    assert "title=" in str_repr