from newsletter2paper.tests.fixtures.articles import article_fixture
from newsletter2paper.tests.fixtures.publications import publication_fixture
from newsletter2paper.tests.fixtures.mock_responses import mock_response_fixture

def setup_module(module):
    # Setup code for the entire module can go here
    pass

def teardown_module(module):
    # Teardown code for the entire module can go here
    pass

def test_article_fixture():
    assert article_fixture is not None

def test_publication_fixture():
    assert publication_fixture is not None

def test_mock_response_fixture():
    assert mock_response_fixture is not None