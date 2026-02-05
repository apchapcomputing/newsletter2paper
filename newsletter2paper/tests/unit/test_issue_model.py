import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.issue import Issue


@pytest.fixture
def sample_issue():
    """Create a sample issue with required fields."""
    return Issue(
        format="newspaper",
        frequency="weekly",
        target_email="test@example.com"
    )


def test_issue_creation(sample_issue):
    """Test that an issue can be created with required fields."""
    assert sample_issue.format == "newspaper"
    assert sample_issue.frequency == "weekly"
    assert sample_issue.target_email == "test@example.com"


def test_issue_format_validation():
    """Test issue format options."""
    # Valid formats: newspaper, essay
    newspaper_issue = Issue(format="newspaper", frequency="daily")
    essay_issue = Issue(format="essay", frequency="monthly")
    
    assert newspaper_issue.format == "newspaper"
    assert essay_issue.format == "essay"


def test_issue_optional_fields():
    """Test issue with optional fields."""
    issue = Issue(
        format="newspaper",
        frequency="weekly",
        target_email="user@example.com"
    )
    # target_email is optional
    assert issue.target_email == "user@example.com"