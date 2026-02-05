import pytest

@pytest.fixture(scope='session')
def db_connection():
    # Setup database connection
    connection = create_db_connection()
    yield connection
    # Teardown database connection
    connection.close()

@pytest.fixture
def sample_article():
    return {
        'title': 'Sample Article',
        'content': 'This is a sample article for testing.',
        'author': 'Author Name'
    }

@pytest.fixture
def sample_publication():
    return {
        'name': 'Sample Publication',
        'issue_number': 1,
        'year': 2023
    }

@pytest.fixture
def mock_api_response():
    return {
        'status': 'success',
        'data': []
    }