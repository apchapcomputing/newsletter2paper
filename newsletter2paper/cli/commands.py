import click
from newsletter2paper.services import rss_service, content_service, pdf_service, email_service

@click.group()
def cli():
    """Newsletter to Paper CLI"""
    pass

@cli.command()
@click.argument('url')
def discover_feed(url):
    """Discover RSS feed from webpage URL"""
    pass

@cli.command()
@click.argument('feed_url')
def process_feed(feed_url):
    """Process RSS feed and store content"""
    pass

@cli.command()
@click.option('--format', type=click.Choice(['newspaper', 'essay']), default='newspaper')
@click.option('--email', required=True)
def generate_paper(format, email):
    """Generate and send paper"""
    pass

if __name__ == '__main__':
    cli()