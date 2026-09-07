import os

# AWS Configuration
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_KEY')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
S3_BUCKET = os.environ.get('S3_BUCKET')

# Email Configuration (legacy SMTP – kept for reference)
SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')

# Resend email delivery
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
# Sender address – must be a verified domain in your Resend account
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'Newsletter2Paper <newsletters@newsletter2paper.xyz>')

# Application Settings
DEFAULT_PAPER_FORMAT = 'newspaper'
CONTENT_CACHE_TTL = 3600  # 1 hour
MAX_ARTICLES_PER_PAPER = 50