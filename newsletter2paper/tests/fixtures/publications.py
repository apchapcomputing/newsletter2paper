from datetime import datetime

def get_publication_fixture():
    return {
        "title": "Sample Publication",
        "date": datetime(2023, 1, 1),
        "author": "John Doe",
        "content": "This is a sample publication content.",
        "status": "published"
    }

publications = [
    get_publication_fixture(),
    {
        "title": "Another Publication",
        "date": datetime(2023, 2, 1),
        "author": "Jane Smith",
        "content": "This is another sample publication content.",
        "status": "draft"
    }
]