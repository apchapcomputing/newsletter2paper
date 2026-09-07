import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:
    BackgroundScheduler = None
from sqlalchemy import create_engine, text
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from services.go_pdf_service import GoPDFService
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class SchedulerService:
    """Background scheduler that finds due issues, locks them and generates PDFs."""

    def __init__(self, interval_seconds: int = 60, batch_size: int = 5):
        self.interval_seconds = interval_seconds
        self.batch_size = batch_size
        # Create scheduler only if APScheduler is available in the environment.
        if BackgroundScheduler is not None:
            self.scheduler = BackgroundScheduler()
        else:
            self.scheduler = None
        self.db_url = os.environ.get('SUPABASE_DATABASE_URL')
        if not self.db_url:
            raise RuntimeError('SUPABASE_DATABASE_URL is required for scheduler')

        # Some managed Postgres connection strings (e.g. Supabase) may include
        # non-standard query params like `pgbouncer=true` which psycopg2/libpq
        # treats as an invalid connection option. Strip unsupported params here
        # so SQLAlchemy/psycopg2 can connect.
        try:
            parsed = urlparse(self.db_url)
            qs = dict(parse_qsl(parsed.query))
            if 'pgbouncer' in qs:
                qs.pop('pgbouncer', None)
                sanitized = parsed._replace(query=urlencode(qs, doseq=True))
                self.db_url = sanitized.geturl()
                logger.info('Sanitized SUPABASE_DATABASE_URL by removing unsupported query params')
        except Exception:
            # If parsing fails, leave the original URL and let create_engine raise a clear error
            logger.debug('Failed to sanitize SUPABASE_DATABASE_URL; using original value')

        # Create a SQLAlchemy engine for direct Postgres access (FOR UPDATE SKIP LOCKED)
        self.engine = create_engine(self.db_url, pool_pre_ping=True)

        # Reuse the Go PDF service instance
        self.pdf_service = GoPDFService(use_docker=True, shared_dir="/shared")

    def start(self) -> None:
        logger.info("Starting SchedulerService")
        # If APScheduler isn't installed, we can't start the background scheduler.
        if self.scheduler is None:
            logger.warning("APScheduler not available; scheduler won't run. Install 'apscheduler' to enable background jobs.")
            return

        # Add job to run periodically
        self.scheduler.add_job(self._job_check_and_process, 'interval', seconds=self.interval_seconds, id='scheduler_check')
        self.scheduler.start()

    def shutdown(self) -> None:
        logger.info("Shutting down SchedulerService")
        try:
            if self.scheduler is not None:
                self.scheduler.shutdown(wait=False)
        except Exception:
            logger.exception("Failed to shutdown scheduler cleanly")

    def _job_check_and_process(self) -> None:
        """Synchronous job invoked by APScheduler."""
        logger.debug("Scheduler tick: checking for due issues")
        try:
            with self.engine.begin() as conn:
                # Lock due rows to avoid double-processing
                sql = text(
                    """
                    SELECT id
                    FROM public.issues
                    WHERE auto_send = true
                      AND (next_run_at IS NULL OR next_run_at <= now())
                      AND schedule_status = 'idle'
                    ORDER BY next_run_at NULLS FIRST
                    FOR UPDATE SKIP LOCKED
                    LIMIT :limit
                    """
                )
                rows = conn.execute(sql, {"limit": self.batch_size}).fetchall()
                issue_ids = [r[0] for r in rows]

                # Mark selected rows as processing and set locked_at
                if issue_ids:
                    upd = text(
                        "UPDATE public.issues SET schedule_status='processing', locked_at=now() WHERE id = ANY(:ids)"
                    )
                    conn.execute(upd, {"ids": issue_ids})

            # Process each issue outside the lock transaction
            for issue_id in issue_ids:
                try:
                    logger.info(f"Processing scheduled issue {issue_id}")
                    asyncio.run(self._process_issue(issue_id))
                except Exception as e:
                    logger.exception(f"Failed processing issue {issue_id}: {e}")

        except Exception as e:
            logger.exception(f"Scheduler check failed: {e}")

    async def _process_issue(self, issue_id: str) -> None:
        """Fetch articles for issue, generate PDF, send email, and update scheduling fields."""
        db = DatabaseService()

        # Fetch full issue record via supabase client
        issue_result = db.client.table('issues').select('*').eq('id', str(issue_id)).execute()
        if not issue_result.data:
            logger.warning(f"Scheduled issue not found: {issue_id}")
            return
        issue = issue_result.data[0]

        # Determine days_back from article_window_days (fallback to 7)
        days_back = int(issue.get('article_window_days') or 7)

        # Fetch articles using RSSService (async)
        from services.rss_service import RSSService
        rss = RSSService()
        articles_data = await rss.fetch_recent_articles_for_issue(
            issue_id, days_back=days_back, max_articles_per_publication=5
        )

        if not articles_data or articles_data.get('total_articles', 0) == 0:
            logger.info(f"No articles for scheduled issue {issue_id}; marking idle and skipping")
            # Update status back to idle and schedule next_run_at depending on frequency
            self._mark_issue_idle_after_run(issue)
            return

        # Flatten articles
        all_articles = []
        for pub_list in articles_data.get('articles_by_publication', {}).values():
            all_articles.extend(pub_list)

        # Choose layout and remove_images from DB record
        layout_type = issue.get('format', 'newspaper')
        remove_images = issue.get('remove_images', False)

        # Generate PDF
        result = await self.pdf_service.generate_pdf_from_issue(
            issue_id=str(issue_id),
            articles=all_articles,
            issue_info=articles_data.get('issue', {}),
            layout_type=layout_type,
            remove_images=remove_images,
            verbose=False
        )

        now = datetime.now(timezone.utc)

        # Update scheduling fields based on result
        if result.get('success') and result.get('pdf_url'):
            # Send email if configured
            target_email = issue.get('target_email')
            if target_email:
                try:
                    from services.email_service import EmailService
                    email_svc = EmailService()
                    email_svc.send_pdf(email_address=target_email, pdf_url=result['pdf_url'], subject=f"Your scheduled PDF: {issue.get('title')}", issue_title=issue.get('title'))
                except Exception:
                    logger.exception(f"Failed to send scheduled email for issue {issue_id}")

            # Compute next_run_at based on frequency
            next_at = self._compute_next_run(issue, now)

            # Persist success
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE public.issues
                        SET last_run_at = now(), next_run_at = :next_at, schedule_status = 'idle', last_run_error = NULL, updated_at = now()
                        WHERE id = :id
                        """
                    ),
                    {"id": str(issue_id), "next_at": next_at}
                )
            logger.info(f"Scheduled issue {issue_id} processed successfully; next_run_at={next_at}")
        else:
            # Mark failed and schedule retry in 1 hour
            err = result.get('error') or 'unknown error'
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE public.issues
                        SET schedule_status = 'failed', last_run_error = :err, next_run_at = now() + interval '1 hour', updated_at = now()
                        WHERE id = :id
                        """
                    ),
                    {"id": str(issue_id), "err": str(err)}
                )
            logger.warning(f"Scheduled issue {issue_id} failed: {err}")

    def _compute_next_run(self, issue: dict, now: datetime) -> str:
        """Return SQL timestamp string for next run or None."""
        freq = issue.get('frequency', 'weekly')
        if freq == 'daily':
            delta = timedelta(days=1)
        elif freq == 'weekly':
            delta = timedelta(days=7)
        elif freq == 'monthly':
            delta = timedelta(days=30)
        else:
            # For 'once' and 'custom' we disable auto_send
            # Return NULL to indicate no further runs
            # Also disable auto_send explicitly
            with self.engine.begin() as conn:
                conn.execute(text("UPDATE public.issues SET auto_send = false WHERE id = :id"), {"id": issue.get('id')})
            return None

        next_dt = now + delta
        # Return ISO format string compatible with SQL parameter binding
        return next_dt.isoformat()

    def _mark_issue_idle_after_run(self, issue: dict) -> None:
        """Update issue row to idle and compute next_run_at based on frequency."""
        next_at = self._compute_next_run(issue, datetime.now(timezone.utc))
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.issues
                    SET schedule_status = 'idle', next_run_at = :next_at, updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": issue.get('id'), "next_at": next_at}
            )
