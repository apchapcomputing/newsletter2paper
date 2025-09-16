class Article:
    def __init__(self, title, subtitle, date_published, author, publication, url, s3_url=None):
        self.title = title
        self.subtitle = subtitle
        self.date_published = date_published
        self.author = author
        self.publication = publication
        self.url = url
        self.s3_url = s3_url