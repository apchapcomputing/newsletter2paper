import click
from services import rss_service
from services.database_service import DatabaseService
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """newsletter2paper cli"""
    pass

@cli.command()
@click.argument('url')
def discover_feed(url):
    """Discover RSS feed from webpage URL"""
    rss = rss_service.RSSService()
    try:
        feed_url = rss.get_feed_url(url)
        if feed_url:
            click.echo(f"Found feed URL: {feed_url}")
        else:
            click.echo(f"No feed URL found for {url}", err=True)
            exit(1)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        exit(1)

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

@cli.command()
@click.option('--days', type=int, default=14, help='Delete issues older than this many days (default: 14)')
@click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
@click.option('--verbose', is_flag=True, help='Show detailed cleanup information')
def cleanup_guest_newspapers(days, dry_run, verbose):
    """Clean up old guest newspapers and orphaned data"""
    try:
        db_service = DatabaseService()
        client = db_service.client

        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        if verbose:
            click.echo(f"🗑️  Starting cleanup for issues older than {days} days ({cutoff_date})")
            click.echo("=" * 60)

        # Find old guest issues (no user association)
        old_issues = client.table('issues').select('id, title, created_at').lt(
            'created_at', cutoff_date
        ).execute()

        if not old_issues.data:
            click.echo("✅ No old guest issues found. Nothing to clean up.")
            return

        # Filter to only those without users
        guest_issues_to_delete = []
        for issue in old_issues.data:
            user_issues = client.table('user_issues').select('user_id').eq(
                'issue_id', issue['id']
            ).execute()
            if not user_issues.data:
                guest_issues_to_delete.append(issue)

        if not guest_issues_to_delete:
            click.echo("✅ No old guest issues without users. Nothing to clean up.")
            return

        issue_ids_to_delete = [issue['id'] for issue in guest_issues_to_delete]

        if verbose:
            click.echo(f"Found {len(guest_issues_to_delete)} old guest issues to delete:")
            for issue in guest_issues_to_delete:
                click.echo(f"  - {issue['title']} (created: {issue['created_at']})")

        if dry_run:
            click.echo(f"\n[DRY RUN] Would delete {len(guest_issues_to_delete)} issues")
            click.echo("Run without --dry-run to actually delete")
            return

        # Delete issue_publications relationships first (due to foreign keys)
        for issue_id in issue_ids_to_delete:
            client.table('issue_publications').delete().eq('issue_id', issue_id).execute()

        # Delete the issues
        issues_deleted = 0
        for issue_id in issue_ids_to_delete:
            client.table('issues').delete().eq('id', issue_id).execute()
            issues_deleted += 1

        # Clean up orphaned articles
        all_articles = client.table('articles').select('id, publication_id').execute()
        articles_to_delete = []

        for article in all_articles.data:
            linked_issues = client.table('issue_publications').select('issue_id').eq(
                'publication_id', article['publication_id']
            ).execute()
            if not linked_issues.data:
                articles_to_delete.append(article['id'])

        articles_deleted = 0
        for article_id in articles_to_delete:
            client.table('articles').delete().eq('id', article_id).execute()
            articles_deleted += 1

        # Clean up orphaned publications
        all_publications = client.table('publications').select('id').execute()
        publications_to_delete = []

        for pub in all_publications.data:
            linked_issues = client.table('issue_publications').select('issue_id').eq(
                'publication_id', pub['id']
            ).execute()
            if not linked_issues.data:
                publications_to_delete.append(pub['id'])

        publications_deleted = 0
        for pub_id in publications_to_delete:
            client.table('publications').delete().eq('id', pub_id).execute()
            publications_deleted += 1

        click.echo(f"\n✅ Cleanup completed successfully!")
        click.echo(f"  - Issues deleted: {issues_deleted}")
        click.echo(f"  - Articles deleted: {articles_deleted}")
        click.echo(f"  - Publications deleted: {publications_deleted}")

    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
        click.echo(f"❌ Error during cleanup: {str(e)}", err=True)
        exit(1)

if __name__ == '__main__':
    cli()