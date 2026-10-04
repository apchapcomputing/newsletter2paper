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
from services.email_service import PERMANENT, TRANSIENT, SendResult
from services.delivery_store import CADENCE_COLUMNS, CLOSED_STATUSES, Claim, ClaimLost, DeliveryStore, SendNowCooldown  # noqa: F401

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_MINUTES = int(os.environ.get('SCHEDULER_LOCK_TIMEOUT_MINUTES', '15'))
MAX_RUN_ATTEMPTS = int(os.environ.get('SCHEDULER_MAX_ATTEMPTS', '5'))
MAX_BACKOFF = timedelta(hours=24)
# Minimum gap between a send-now and the issue's previous claim (locked_at is never cleared,
# so it doubles as "last run started"); caps PDF/email load per issue.
SEND_NOW_COOLDOWN_MINUTES = int(os.environ.get('SEND_NOW_COOLDOWN_MINUTES', '10'))
# Worst-case run = RSS fetch (sequential, 30s timeout per feed) + PDF render timeout + email.
# The lock timeout must exceed it, or a slow run is reclaimed while still working (fencing then
# stops the slower worker, but the edition is generated twice).
RSS_BUDGET_SECONDS = int(os.environ.get('SCHEDULER_RSS_BUDGET_SECONDS', '300'))
EMAIL_BUDGET_SECONDS = 60
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


def period_key(frequency: str, scheduled_for: datetime, tz_name: Optional[str] = None) -> str:
    """Identifier of the delivery period the slot `scheduled_for` belongs to.

    Computed from the slot, never processing time, so a late retry stays in its period.
    One-shot frequencies key on the slot itself: each enablement is its own edition.
    """
    if frequency in ONE_SHOT_FREQUENCIES:
        return f"once-{scheduled_for.astimezone(timezone.utc).isoformat()}"
    local = scheduled_for.astimezone(_resolve_tz(tz_name))
    if frequency == 'daily':
        return local.strftime('%Y-%m-%d')
    if frequency == 'weekly':
        iso = local.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if frequency == 'monthly':
        return local.strftime('%Y-%m')
    return f"once-{scheduled_for.astimezone(timezone.utc).isoformat()}"


def check_lock_timeout(lock_timeout_minutes: int, render_timeout_seconds: int) -> None:
    worst_case = RSS_BUDGET_SECONDS + render_timeout_seconds + EMAIL_BUDGET_SECONDS
    if lock_timeout_minutes * 60 <= worst_case:
        raise RuntimeError(
            f"SCHEDULER_LOCK_TIMEOUT_MINUTES={lock_timeout_minutes} must exceed the worst-case run "
            f"({worst_case}s = RSS {RSS_BUDGET_SECONDS}s + render {render_timeout_seconds}s + email {EMAIL_BUDGET_SECONDS}s)"
        )


def _parse_ts(value) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))


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

        self.store = DeliveryStore(self.engine)

        # Reuse the Go PDF service instance
        self.pdf_service = GoPDFService(use_docker=True, shared_dir="/shared")
        check_lock_timeout(LOCK_TIMEOUT_MINUTES, self.pdf_service.default_timeout)

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
        """Synchronous job invoked by APScheduler.

        Issues are claimed one at a time, so a claim's lock age is its own run time and never
        includes time spent waiting behind other issues in the batch.
        """
        logger.debug("Scheduler tick: checking for due issues")
        try:
            self._initialize_unscheduled()
            for _ in range(self.batch_size):
                claim = self.store.claim_next_due(LOCK_TIMEOUT_MINUTES)
                if claim is None:
                    break
                logger.info(f"Processing scheduled issue {claim.issue_id}")
                try:
                    asyncio.run(self._process_issue(claim))
                except Exception as e:
                    logger.exception(f"Failed processing issue {claim.issue_id}: {e}")
                    self.release_after_error(claim, f"unexpected error: {e}")
        except Exception as e:
            logger.exception(f"Scheduler check failed: {e}")

    def _initialize_unscheduled(self) -> None:
        """Give auto_send issues without next_run_at their first cadence boundary.

        Enabling auto_send must not send immediately; the user can use "send now" for that.
        Non-repeating frequencies ('once'/'custom') are due right away.
        """
        def first_run(frequency, tz_name):
            now = datetime.now(timezone.utc)
            return compute_next_run(frequency, now, tz_name) or now

        for issue_id, next_at in self.store.initialize_unscheduled(first_run):
            logger.info(f"Initialised schedule for issue {issue_id}: next_run_at={next_at}")

    def claim_for_send_now(self, issue_id: str) -> Optional[Claim]:
        """Lock one issue for a manual send. Returns the claim to pass to `send_now`, or None if it
        is already being processed. Raises SendNowCooldown if the issue was claimed (manually or
        by the poll) within SEND_NOW_COOLDOWN_MINUTES."""
        return self.store.claim_for_send_now(issue_id, LOCK_TIMEOUT_MINUTES, SEND_NOW_COOLDOWN_MINUTES)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    async def send_now(self, claim: Claim) -> dict:
        """Generate and email an issue immediately as a manual delivery, without touching its
        cadence. Call `claim_for_send_now` first."""
        return await self._process_issue(claim, force=True)

    async def _process_issue(self, claim: Claim, force: bool = False) -> dict:
        """Run one edition: open its delivery, render (or reuse) the PDF, email it, record the outcome.

        force=True is the manual "send now" path: a separate manual delivery, no retries, and the
        cadence (next_run_at, the scheduled delivery) is left alone.
        Returns {'success': bool, 'error': Optional[str]}.
        """
        try:
            return await self._run(claim, force)
        except ClaimLost:
            logger.warning(f"Issue {claim.issue_id}: claim was taken over by another worker; stopping without writing")
            return {'success': False, 'error': 'claim lost'}

    async def _run(self, claim: Claim, force: bool) -> dict:
        issue = self._load_issue(claim.issue_id)
        if not issue:
            logger.warning(f"Scheduled issue not found: {claim.issue_id}")
            return {'success': False, 'error': 'issue not found'}

        now = datetime.now(timezone.utc)
        if force:
            delivery = self.store.create_manual_delivery(claim)
        else:
            scheduled_for = _parse_ts(issue.get('next_run_at')) or now
            key = period_key(issue.get('frequency', 'weekly'), scheduled_for, issue.get('schedule_timezone'))
            delivery = self.store.open_scheduled_delivery(claim, scheduled_for, key)
            if delivery['status'] in CLOSED_STATUSES:
                logger.info(f"Issue {claim.issue_id} already handled period {key} ({delivery['status']}); skipping")
                self._advance(claim, issue, now)
                return {'success': True, 'error': None}

        # Already 'sending' means a previous run may have reached Resend: retry with the same
        # attempt number, hence the same idempotency key, so Resend drops the duplicate.
        in_flight = delivery['status'] == 'sending'
        try:
            target_email = (issue.get('target_email') or '').strip()
            if not target_email:
                # Rendering a PDF nobody receives is not a delivery.
                error = "config: no recipient email address is set"
                self._fail(claim, issue, delivery, error, now, force, error_kind=PERMANENT)
                return {'success': False, 'error': error}

            pdf_url = delivery.get('pdf_url')
            if pdf_url:
                logger.info(f"Issue {claim.issue_id}: reusing PDF from delivery {delivery['id']}, retrying email only")
            else:
                result = await self._generate_pdf(issue)
                if result is None:
                    logger.info(f"No articles for issue {claim.issue_id}; skipping")
                    self._skip(claim, issue, delivery, now, force)
                    return {'success': True, 'error': None}
                if not (result.get('success') and result.get('pdf_url')):
                    err = str(result.get('error') or 'unknown error')
                    self._fail(claim, issue, delivery, f"pdf: {err}", now, force)
                    return {'success': False, 'error': err}
                pdf_url = result['pdf_url']

            self.store.mark_sending(claim, delivery['id'], pdf_url, target_email)
            in_flight = True
            idempotency_key = f"delivery-{delivery['id']}-{delivery['attempts']}"
            sent = self._send_email(issue, target_email, pdf_url, idempotency_key)
            if not sent.ok:
                self._fail(claim, issue, delivery, sent.error, now, force,
                           error_kind=sent.error_kind, retry_after=sent.retry_after)
                return {'success': False, 'error': sent.error}

            self._succeed(claim, issue, delivery, pdf_url, sent.message_id, now, force)
            return {'success': True, 'error': None}
        except ClaimLost:
            raise
        except Exception as e:
            logger.exception(f"Issue {claim.issue_id}: unexpected error in delivery {delivery['id']}")
            # Don't change the idempotency key once the email may have been accepted.
            self._fail(claim, issue, delivery, f"unexpected error: {e}", now, force, count_attempt=not in_flight)
            return {'success': False, 'error': str(e)}

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

    def _send_email(self, issue: dict, target_email: str, pdf_url: str, idempotency_key: str) -> SendResult:
        try:
            from services.email_service import EmailService
            return EmailService().send(
                email_address=target_email,
                pdf_url=pdf_url,
                subject=f"Your scheduled PDF: {issue.get('title')}",
                issue_title=issue.get('title'),
                idempotency_key=idempotency_key,
            )
        except Exception as e:
            logger.exception(f"Failed to send scheduled email for issue {issue['id']}")
            return SendResult.failed(TRANSIENT, f"email: unexpected error ({e})")

    # ------------------------------------------------------------------
    # State transitions (every write goes through the fenced store)
    # ------------------------------------------------------------------

    @staticmethod
    def _cadence(issue: dict) -> dict:
        """The cadence this run loaded, so the final write can tell if the owner changed it since."""
        return {col: issue.get(col) for col in CADENCE_COLUMNS if col in issue}

    def _next_slot(self, issue: dict, now: datetime) -> dict:
        """Issue fields that release it to its next slot; one-shot frequencies turn auto_send off."""
        next_at = compute_next_run(issue.get('frequency', 'weekly'), now, issue.get('schedule_timezone'))
        fields = {'schedule_status': 'idle', 'next_run_at': next_at}
        if next_at is None:
            fields['auto_send'] = False
        return fields

    def _advance(self, claim: Claim, issue: dict, now: datetime) -> None:
        self.store.finish(claim, self._next_slot(issue, now), cadence=self._cadence(issue))

    def _succeed(self, claim, issue, delivery, pdf_url, message_id, now, force) -> None:
        issue_fields = {'schedule_status': claim.previous_status} if force else self._next_slot(issue, now)
        issue_fields.update(last_run_at=now, last_run_error=None)
        self.store.finish(claim, issue_fields, delivery['id'], {
            'status': 'sent', 'sent_at': now, 'pdf_url': pdf_url, 'resend_message_id': message_id,
            'error': None, 'error_kind': None, 'next_attempt_at': None,
        }, cadence=self._cadence(issue))
        logger.info(f"Issue {claim.issue_id} delivered ({'manual' if force else 'scheduled'}, delivery {delivery['id']})")

    def _skip(self, claim, issue, delivery, now, force) -> None:
        issue_fields = {'schedule_status': claim.previous_status} if force else self._next_slot(issue, now)
        self.store.finish(claim, issue_fields, delivery['id'], {'status': 'skipped'}, cadence=self._cadence(issue))

    def _fail(self, claim, issue, delivery, error, now, force, count_attempt=True,
              error_kind=TRANSIENT, retry_after=None) -> None:
        """Record a failed attempt. Transient failures retry with backoff (no sooner than the
        provider's Retry-After); permanent ones (bad recipient, rejected message, missing config)
        abandon the edition at once, since retrying cannot help."""
        logger.warning(f"Issue {claim.issue_id} failed ({error_kind}): {error}")
        attempts = delivery['attempts'] + (1 if count_attempt else 0)
        cadence = self._cadence(issue)
        if force:
            # Manual sends are not retried.
            self.store.finish(
                claim, {'schedule_status': claim.previous_status, 'last_run_error': error},
                delivery['id'], {'status': 'failed', 'attempts': attempts, 'error': error, 'error_kind': error_kind},
                cadence=cadence,
            )
            return
        if error_kind == PERMANENT or attempts >= MAX_RUN_ATTEMPTS:
            # Give up on this edition but keep the schedule alive.
            issue_fields = self._next_slot(issue, now)
            if error_kind != PERMANENT:
                error = f"{error} (gave up after {MAX_RUN_ATTEMPTS} attempts)"
                if issue_fields.get('auto_send') is False:
                    # One-shot issue: try again tomorrow rather than silently turning it off.
                    issue_fields = {'schedule_status': 'idle', 'next_run_at': now + MAX_BACKOFF}
            issue_fields['last_run_error'] = error
            self.store.finish(claim, issue_fields, delivery['id'], {
                'status': 'abandoned', 'attempts': attempts, 'error': error, 'error_kind': error_kind,
                'next_attempt_at': None,
            }, cadence=cadence)
            return
        retry_at = now + max(retry_delay(attempts), timedelta(seconds=retry_after or 0))
        self.store.finish(
            claim, {'schedule_status': 'failed', 'next_run_at': retry_at, 'last_run_error': error},
            delivery['id'], {'status': 'failed', 'attempts': attempts, 'error': error, 'error_kind': error_kind,
                             'next_attempt_at': retry_at},
            cadence=cadence,
        )

    def release_after_error(self, claim: Claim, error: str, force: bool = False) -> None:
        """Last-resort handler for errors before a delivery exists, so rows never stay 'processing'."""
        if force:
            fields = {'schedule_status': claim.previous_status, 'last_run_error': error}
        else:
            fields = {'schedule_status': 'failed', 'last_run_error': error,
                      'next_run_at': datetime.now(timezone.utc) + retry_delay(1)}
        try:
            self.store.finish(claim, fields)
        except ClaimLost:
            logger.warning(f"Issue {claim.issue_id}: claim taken over; not recording error")
        except Exception:
            logger.exception(f"Could not record failure for issue {claim.issue_id}")
