import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:
    BackgroundScheduler = None
from sqlalchemy import create_engine, text
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from services.go_pdf_service import GoPDFService
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_MINUTES = int(os.environ.get('SCHEDULER_LOCK_TIMEOUT_MINUTES', '15'))
MAX_RUN_ATTEMPTS = int(os.environ.get('SCHEDULER_MAX_ATTEMPTS', '5'))
MAX_BACKOFF = timedelta(hours=24)
# Minimum gap between a send-now and the issue's previous claim (locked_at is never cleared,
# so it doubles as "last run started"); caps PDF/email load per issue.
SEND_NOW_COOLDOWN_MINUTES = int(os.environ.get('SEND_NOW_COOLDOWN_MINUTES', '10'))


class SendNowCooldown(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"retry after {retry_after}s")
        self.retry_after = retry_after
# Frequencies that send once and then turn auto_send off; they have no recurring period.
ONE_SHOT_FREQUENCIES = {'once', 'custom'}


def _resolve_tz(tz_name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or 'UTC')
    except Exception:
        logger.warning(f"Unknown schedule_timezone {tz_name!r}; falling back to UTC")
        return ZoneInfo('UTC')


def _add_months(local: datetime, months: int) -> datetime:
    """Add calendar months to a local datetime, clamping the day to the month end."""
    month_index = local.month - 1 + months
    year = local.year + month_index // 12
    month = month_index % 12 + 1
    last_day = (datetime(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return local.replace(year=year, month=month, day=min(local.day, last_day))


def compute_next_run(frequency: str, now: datetime, tz_name: Optional[str] = None) -> Optional[datetime]:
    """Next run after `now` (UTC-aware), keeping the local wall-clock time in `tz_name`.

    Returns None for frequencies that don't repeat ('once', 'custom').
    """
    tz = _resolve_tz(tz_name)
    local = now.astimezone(tz)
    if frequency == 'daily':
        nxt = local.replace(tzinfo=None) + timedelta(days=1)
    elif frequency == 'weekly':
        nxt = local.replace(tzinfo=None) + timedelta(days=7)
    elif frequency == 'monthly':
        nxt = _add_months(local.replace(tzinfo=None), 1)
    else:
        return None
    return nxt.replace(tzinfo=tz).astimezone(timezone.utc)


def period_key(frequency: str, now: datetime, tz_name: Optional[str] = None) -> str:
    """Identifier of the delivery period `now` falls in; used to send at most once per period."""
    local = now.astimezone(_resolve_tz(tz_name))
    if frequency == 'daily':
        return local.strftime('%Y-%m-%d')
    if frequency == 'weekly':
        iso = local.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if frequency == 'monthly':
        return local.strftime('%Y-%m')
    return 'once'


def retry_delay(attempts: int) -> timedelta:
    """Exponential backoff: 1h, 2h, 4h, ... capped at 24h."""
    return min(timedelta(hours=2 ** max(attempts - 1, 0)), MAX_BACKOFF)


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



    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _job_check_and_process(self) -> None:
        """Synchronous job invoked by APScheduler."""
        logger.debug("Scheduler tick: checking for due issues")
        try:
            self._initialize_unscheduled()
            issue_ids = self._claim_due_issues()
            for issue_id in issue_ids:
                try:
                    logger.info(f"Processing scheduled issue {issue_id}")
                    asyncio.run(self._process_issue(issue_id))
                except Exception as e:
                    logger.exception(f"Failed processing issue {issue_id}: {e}")
                    self._record_failure_by_id(issue_id, f"unexpected error: {e}")
        except Exception as e:
            logger.exception(f"Scheduler check failed: {e}")

    def _initialize_unscheduled(self) -> None:
        """Give auto_send issues without next_run_at their first cadence boundary.

        Enabling auto_send must not send immediately; the user can use "send now" for that.
        Non-repeating frequencies ('once'/'custom') are due right away.
        """
        with self.engine.begin() as conn:
            rows = conn.execute(text(
                """
                SELECT id, frequency, schedule_timezone
                FROM public.issues
                WHERE auto_send = true AND next_run_at IS NULL AND schedule_status = 'idle'
                FOR UPDATE SKIP LOCKED
                """
            )).fetchall()
            now = datetime.now(timezone.utc)
            for issue_id, frequency, tz_name in rows:
                next_at = compute_next_run(frequency, now, tz_name) or now
                conn.execute(
                    text("UPDATE public.issues SET next_run_at = :next_at, updated_at = now() WHERE id = :id"),
                    {"id": issue_id, "next_at": next_at},
                )
                logger.info(f"Initialised schedule for issue {issue_id}: next_run_at={next_at}")

    def _claim_due_issues(self) -> List[str]:
        """Lock due rows (including retryable failures and stale locks) and mark them processing."""
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id
                    FROM public.issues
                    WHERE auto_send = true
                      AND next_run_at <= now()
                      AND (
                        schedule_status IN ('idle', 'failed')
                        OR (schedule_status = 'processing'
                            AND locked_at < now() - make_interval(mins => :lock_timeout))
                      )
                    ORDER BY next_run_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT :limit
                    """
                ),
                {"limit": self.batch_size, "lock_timeout": LOCK_TIMEOUT_MINUTES},
            ).fetchall()
            issue_ids = [r[0] for r in rows]
            if issue_ids:
                conn.execute(
                    text("UPDATE public.issues SET schedule_status='processing', locked_at=now() WHERE id = ANY(:ids)"),
                    {"ids": issue_ids},
                )
        return issue_ids

    def claim_for_send_now(self, issue_id: str) -> Optional[str]:
        """Atomically lock one issue for a manual send. Returns the schedule_status to restore
        afterwards, or None if it is already being processed. Raises SendNowCooldown if the
        issue was claimed (manually or by the poll) within SEND_NOW_COOLDOWN_MINUTES."""
        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT schedule_status, locked_at, now() FROM public.issues WHERE id = :id FOR UPDATE"),
                {"id": str(issue_id)},
            ).fetchone()
            if not row:
                return None
            prev, locked_at, db_now = row
            if locked_at is not None:
                age = db_now - locked_at
                if prev == 'processing' and age < timedelta(minutes=LOCK_TIMEOUT_MINUTES):
                    return None
                cooldown = timedelta(minutes=SEND_NOW_COOLDOWN_MINUTES)
                if age < cooldown:
                    raise SendNowCooldown(int((cooldown - age).total_seconds()) + 1)
            conn.execute(
                text("UPDATE public.issues SET schedule_status = 'processing', locked_at = now() WHERE id = :id"),
                {"id": str(issue_id)},
            )
        # A stale 'processing' lock belongs to a crashed run; restoring it would leave the row
        # stuck again, so hand it back to the poll as 'idle' (next_run_at is untouched).
        return 'idle' if prev == 'processing' else prev

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    async def send_now(self, issue_id: str, previous_status: str = 'idle') -> dict:
        """Generate and email an issue immediately without touching its cadence.

        Call `claim_for_send_now` first and pass the returned status.
        """
        return await self._process_issue(issue_id, force=True, previous_status=previous_status)

    async def _process_issue(self, issue_id: str, force: bool = False, previous_status: str = 'idle') -> dict:
        """Generate a PDF (or reuse a pending one), email it, and update scheduling fields.

        force=True is the manual "send now" path: no idempotency check, fresh PDF, and the
        cadence (next_run_at, last_sent_period, retry state) is left alone.
        Returns {'success': bool, 'error': Optional[str]}.
        """
        issue = self._load_issue(issue_id)
        if not issue:
            logger.warning(f"Scheduled issue not found: {issue_id}")
            return {'success': False, 'error': 'issue not found'}

        now = datetime.now(timezone.utc)
        freq = issue.get('frequency', 'weekly')
        tz_name = issue.get('schedule_timezone')
        period = period_key(freq, now, tz_name)

        # One-shot issues are guarded by auto_send turning off after a successful send, and their
        # period key is the constant 'once', so checking it would block every re-enabled send.
        if not force and freq not in ONE_SHOT_FREQUENCIES and issue.get('last_sent_period') == period:
            logger.info(f"Issue {issue_id} already sent for period {period}; skipping")
            self._finalize_idle(issue, now)
            return {'success': True, 'error': None}

        # Email-only retry: the PDF for this period was generated but not delivered.
        pdf_url = None
        if not force and issue.get('pending_pdf_url') and issue.get('pending_period') == period:
            pdf_url = issue['pending_pdf_url']
            logger.info(f"Issue {issue_id}: reusing pending PDF, retrying email only")
        else:
            result = await self._generate_pdf(issue)
            if result is None:
                logger.info(f"No articles for scheduled issue {issue_id}; skipping")
                self._finalize_idle(issue, now, force=force, previous_status=previous_status)
                return {'success': True, 'error': None}
            if not (result.get('success') and result.get('pdf_url')):
                err = str(result.get('error') or 'unknown error')
                self._finalize_failure(issue, f"pdf: {err}", now, force, previous_status)
                return {'success': False, 'error': err}
            pdf_url = result['pdf_url']

        target_email = issue.get('target_email')
        if target_email and not self._send_email(issue, target_email, pdf_url):
            # Keep the PDF so the retry only resends the email.
            if not force:
                self._store_pending(issue_id, pdf_url, period)
            self._finalize_failure(issue, "email: delivery failed", now, force, previous_status)
            return {'success': False, 'error': 'email delivery failed'}

        self._finalize_success(issue, period, now, force, previous_status)
        return {'success': True, 'error': None}

    def _load_issue(self, issue_id: str) -> Optional[dict]:
        db = DatabaseService()
        result = db.client.table('issues').select('*').eq('id', str(issue_id)).execute()
        return result.data[0] if result.data else None

    async def _generate_pdf(self, issue: dict) -> Optional[dict]:
        """Fetch articles and render the PDF. Returns None when there are no articles."""
        issue_id = issue['id']
        days_back = int(issue.get('article_window_days') or 7)

        from services.rss_service import RSSService
        rss = RSSService()
        articles_data = await rss.fetch_recent_articles_for_issue(
            issue_id, days_back=days_back, max_articles_per_publication=5
        )
        if not articles_data or articles_data.get('total_articles', 0) == 0:
            return None

        all_articles = []
        for pub_list in articles_data.get('articles_by_publication', {}).values():
            all_articles.extend(pub_list)

        return await self.pdf_service.generate_pdf_from_issue(
            issue_id=str(issue_id),
            articles=all_articles,
            issue_info=articles_data.get('issue', {}),
            layout_type=issue.get('format', 'newspaper'),
            remove_images=issue.get('remove_images', False),
            verbose=False,
        )

    def _send_email(self, issue: dict, target_email: str, pdf_url: str) -> bool:
        try:
            from services.email_service import EmailService
            return bool(EmailService().send_pdf(
                email_address=target_email,
                pdf_url=pdf_url,
                subject=f"Your scheduled PDF: {issue.get('title')}",
                issue_title=issue.get('title'),
            ))
        except Exception:
            logger.exception(f"Failed to send scheduled email for issue {issue['id']}")
            return False

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _store_pending(self, issue_id: str, pdf_url: str, period: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE public.issues SET pending_pdf_url = :url, pending_period = :period WHERE id = :id"),
                {"id": str(issue_id), "url": pdf_url, "period": period},
            )

    def _finalize_success(self, issue: dict, period: str, now: datetime, force: bool, previous_status: str) -> None:
        issue_id = str(issue['id'])
        if force:
            # Manual send: leave cadence and retry state alone.
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE public.issues
                        SET last_run_at = now(), schedule_status = :status, last_run_error = NULL, updated_at = now()
                        WHERE id = :id
                        """
                    ),
                    {"id": issue_id, "status": previous_status},
                )
            logger.info(f"Issue {issue_id} sent manually")
            return

        next_at = compute_next_run(issue.get('frequency', 'weekly'), now, issue.get('schedule_timezone'))
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.issues
                    SET last_run_at = now(), next_run_at = :next_at, schedule_status = 'idle',
                        last_run_error = NULL, run_attempts = 0, last_sent_period = :period,
                        pending_pdf_url = NULL, pending_period = NULL,
                        auto_send = CASE WHEN CAST(:next_at AS timestamptz) IS NULL THEN false ELSE auto_send END,
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": issue_id, "next_at": next_at, "period": period},
            )
        logger.info(f"Scheduled issue {issue_id} processed successfully; next_run_at={next_at}")

    def _finalize_idle(self, issue: dict, now: datetime, force: bool = False, previous_status: str = 'idle') -> None:
        """Nothing to send this time (no articles, or period already delivered)."""
        issue_id = str(issue['id'])
        with self.engine.begin() as conn:
            if force:
                conn.execute(
                    text("UPDATE public.issues SET schedule_status = :status, updated_at = now() WHERE id = :id"),
                    {"id": issue_id, "status": previous_status},
                )
                return
            next_at = compute_next_run(issue.get('frequency', 'weekly'), now, issue.get('schedule_timezone'))
            conn.execute(
                text(
                    """
                    UPDATE public.issues
                    SET schedule_status = 'idle', next_run_at = :next_at,
                        auto_send = CASE WHEN CAST(:next_at AS timestamptz) IS NULL THEN false ELSE auto_send END,
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": issue_id, "next_at": next_at},
            )

    def _finalize_failure(self, issue: dict, error: str, now: datetime, force: bool, previous_status: str) -> None:
        issue_id = str(issue['id'])
        logger.warning(f"Scheduled issue {issue_id} failed: {error}")
        with self.engine.begin() as conn:
            if force:
                conn.execute(
                    text(
                        "UPDATE public.issues SET schedule_status = :status, last_run_error = :err, updated_at = now() WHERE id = :id"
                    ),
                    {"id": issue_id, "status": previous_status, "err": error},
                )
                return

            attempts = int(issue.get('run_attempts') or 0) + 1
            if attempts >= MAX_RUN_ATTEMPTS:
                # Give up for this period but keep the schedule alive.
                next_at = compute_next_run(issue.get('frequency', 'weekly'), now, issue.get('schedule_timezone')) \
                    or now + MAX_BACKOFF
                status, attempts = 'idle', 0
                error = f"{error} (gave up after {MAX_RUN_ATTEMPTS} attempts)"
                clear_pending = True
            else:
                next_at = now + retry_delay(attempts)
                status = 'failed'
                clear_pending = False
            conn.execute(
                text(
                    """
                    UPDATE public.issues
                    SET schedule_status = :status, last_run_error = :err, run_attempts = :attempts,
                        next_run_at = :next_at,
                        pending_pdf_url = CASE WHEN :clear THEN NULL ELSE pending_pdf_url END,
                        pending_period = CASE WHEN :clear THEN NULL ELSE pending_period END,
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": issue_id, "status": status, "err": error,
                 "attempts": attempts, "next_at": next_at, "clear": clear_pending},
            )

    def _record_failure_by_id(self, issue_id: str, error: str, force: bool = False, previous_status: str = 'idle') -> None:
        """Last-resort handler for unexpected exceptions so rows never stay 'processing'."""
        try:
            issue = self._load_issue(issue_id)
            if issue:
                self._finalize_failure(issue, error, datetime.now(timezone.utc), force, previous_status)
        except Exception:
            logger.exception(f"Could not record failure for issue {issue_id}")
