from pytest import fixture

@fixture(scope='session')
def setup_database():
    pass

@fixture
def sample_article():
    return {
        'title': 'Sample Article',
        'content': 'This is a sample article for testing purposes.'
    }

@fixture
def sample_publication():
    return {
        'name': 'Sample Publication',
        'issue': '1',
        'articles': []
    }