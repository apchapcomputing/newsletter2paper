# newsletter2paper cli

This is a CLI that is deployed as AWS Lambda functions.


## Database Schema


### User

- email

- username

- password

- first name

- last name

- papers


### Article

- title

- subtitle

- date published

- author

- publication

- url to content on internet

- AWS S3 url


### Publication

- title

- url to webpage

- RSS feed url

- publisher


### Papers

- publications

- format (newspaper or essay layout)

- email to send PDF to

- frequency to pull articles, generate PDF, and send in email


## Capabilities

- get RSS feed URL from given URL

- get metadata from RSS feed and store in Publications

- get XML content from RSS and store in Articles

- transform XML to HTML content and store in AWS S3

- style and format HTML content for newspaper and essay layouts

- generate PDF from HTML content of Articles within Paper's frequency and in Paper's publications

- send PDF to Paper's email (or User's email, by default)


## Project Structure

```
newsletter2paper/
├── __init__.py
├── config/
│   ├── __init__.py
│   └── settings.py         # Configuration settings for AWS, email, etc.
├── cli/
│   ├── __init__.py
│   └── commands.py         # CLI command implementations
├── models/
│   ├── __init__.py
│   ├── user.py            # User model
│   ├── article.py         # Article model
│   ├── publication.py     # Publication model
│   └── paper.py           # Paper model
├── services/
│   ├── __init__.py
│   ├── rss_service.py     # RSS feed discovery and processing
│   ├── content_service.py # HTML content transformation
│   ├── storage_service.py # AWS S3 storage operations
│   ├── pdf_service.py     # PDF generation
│   └── email_service.py   # Email sending functionality
├── templates/
│   ├── newspaper.html     # Template for newspaper layout
│   └── essay.html         # Template for essay layout
├── styles/
│   ├── newspaper.css      # Styles for newspaper layout
│   └── essay.css          # Styles for essay layout
├── utils/
│   ├── __init__.py
│   └── helpers.py         # Common utility functions
├── tests/
│   ├── __init__.py
│   ├── test_rss_service.py
│   ├── test_content_service.py
│   ├── test_pdf_service.py
│   └── test_email_service.py
├── requirements.txt       # Project dependencies
└── setup.py               # Package setup and metadata
```