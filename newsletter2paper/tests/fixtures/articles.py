from datetime import datetime

def get_article_fixture():
    return {
        "title": "Sample Article",
        "content": "This is a sample article content.",
        "author": "Author Name",
        "published_date": datetime.now().isoformat()
    }

def get_articles_fixture():
    return [
        get_article_fixture(),
        {
            "title": "Another Article",
            "content": "This is another sample article content.",
            "author": "Another Author",
            "published_date": datetime.now().isoformat()
        }
    ]