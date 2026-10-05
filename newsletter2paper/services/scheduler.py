import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:
    BackgroundScheduler = None
from sqlalchemy import create_engine, text
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from services.go_pdf_service import GoPDFService
from services.database_service import DatabaseService
from services.email_service import PERMANENT, TRANSIENT, SendResult
from services.scheduling import (  # noqa: F401
    MAX_BACKOFF, ONE_SHOT_FREQUENCIES, first_slot, next_slot_after_delivery, period_key, retry_deadline, retry_delay,
)
from services.delivery_store import CADENCE_COLUMNS, CLOSED_STATUSES, Claim, ClaimLost, DeliveryStore, SendNowCooldown  # noqa: F401

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_MINUTES = int(os.environ.get('SCHEDULER_LOCK_TIMEOUT_MINUTES', '15'))
MAX_RUN_ATTEMPTS = int(os.environ.get('SCHEDULER_MAX_ATTEMPTS', '5'))
# Minimum gap between a send-now and the issue's previous claim (locked_at is never cleared,
# so it doubles as "last run started"); caps PDF/email load per issue.
SEND_NOW_COOLDOWN_MINUTES = int(os.environ.get('SEND_NOW_COOLDOWN_MINUTES', '10'))
# Worst-case run = RSS fetch (sequential, 30s timeout per feed) + PDF render timeout + email.
# The lock timeout must exceed it, or a slow run is reclaimed while still working (fencing then
# stops the slower worker, but the edition is generated twice).
RSS_BUDGET_SECONDS = int(os.environ.get('SCHEDULER_RSS_BUDGET_SECONDS', '300'))
EMAIL_BUDGET_SECONDS = 60


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
            self._notify_pending_owners()
        except Exception as e:
            logger.exception(f"Scheduler check failed: {e}")

    def _initialize_unscheduled(self) -> None:
        """Give auto_send issues without next_run_at their first cadence boundary.

        Enabling auto_send must not send immediately; the user can use "send now" for that.
        Non-repeating frequencies ('once'/'custom') are due right away.
        """
        def first_run(issue):
            now = datetime.now(timezone.utc)
            return first_slot(issue, now) or now

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
                self._advance(claim, issue, delivery, now)
                return {'success': True, 'error': None}

        # Already 'sending' means a previous run may have reached Resend: its stored idempotency
        # key is reused, so Resend drops the duplicate.
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

            # A stored key belongs to a send whose outcome is unknown; otherwise start a new one.
            idempotency_key = delivery.get('idempotency_key') or f"delivery-{delivery['id']}-{delivery['attempts']}"
            self.store.mark_sending(claim, delivery['id'], pdf_url, target_email, idempotency_key)
            in_flight = True
            sent = self._send_email(issue, target_email, pdf_url, idempotency_key)
            if not sent.ok:
                self._fail(claim, issue, delivery, sent.error, now, force, error_kind=sent.error_kind,
                           retry_after=sent.retry_after, keep_key=sent.outcome_unknown)
                return {'success': False, 'error': sent.error}

            self._succeed(claim, issue, delivery, pdf_url, sent.message_id, now, force)
            return {'success': True, 'error': None}
        except ClaimLost:
            raise
        except Exception as e:
            logger.exception(f"Issue {claim.issue_id}: unexpected error in delivery {delivery['id']}")
            # Once the email may have been accepted, the retry must reuse its idempotency key.
            self._fail(claim, issue, delivery, f"unexpected error: {e}", now, force, keep_key=in_flight)
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
            return SendResult.failed(TRANSIENT, f"email: unexpected error ({e})", outcome_unknown=True)

    # ------------------------------------------------------------------
    # State transitions (every write goes through the fenced store)
    # ------------------------------------------------------------------

    @staticmethod
    def _cadence(issue: dict) -> dict:
        """The cadence this run loaded, so the final write can tell if the owner changed it since."""
        return {col: issue.get(col) for col in CADENCE_COLUMNS if col in issue}

    @staticmethod
    def _slot(delivery: dict, now: datetime) -> datetime:
        """The slot this edition serves. A retry runs later but still serves its original slot."""
        return _parse_ts(delivery.get('scheduled_for')) or now

    def _next_slot(self, issue: dict, delivery: dict, now: datetime) -> dict:
        """Issue fields that release it to the slot after the edition just served (anchored to that
        slot, not to `now`); one-shot frequencies turn auto_send off."""
        next_at = next_slot_after_delivery(issue, self._slot(delivery, now), now)
        fields = {'schedule_status': 'idle', 'next_run_at': next_at}
        if next_at is None:
            fields['auto_send'] = False
        return fields

    def _advance(self, claim: Claim, issue: dict, delivery: dict, now: datetime) -> None:
        self.store.finish(claim, self._next_slot(issue, delivery, now), cadence=self._cadence(issue))

    def _succeed(self, claim, issue, delivery, pdf_url, message_id, now, force) -> None:
        issue_fields = {'schedule_status': claim.previous_status} if force else self._next_slot(issue, delivery, now)
        issue_fields.update(last_run_at=now, last_run_error=None)
        self.store.finish(claim, issue_fields, delivery['id'], {
            'status': 'sent', 'sent_at': now, 'pdf_url': pdf_url, 'resend_message_id': message_id,
            'error': None, 'error_kind': None, 'next_attempt_at': None,
        }, cadence=self._cadence(issue))
        logger.info(f"Issue {claim.issue_id} delivered ({'manual' if force else 'scheduled'}, delivery {delivery['id']})")

    def _skip(self, claim, issue, delivery, now, force) -> None:
        issue_fields = {'schedule_status': claim.previous_status} if force else self._next_slot(issue, delivery, now)
        self.store.finish(claim, issue_fields, delivery['id'], {'status': 'skipped'}, cadence=self._cadence(issue))

    def _fail(self, claim, issue, delivery, error, now, force, error_kind=TRANSIENT, retry_after=None,
              keep_key=False) -> None:
        """Record a failed attempt. Transient failures retry with backoff (no sooner than the
        provider's Retry-After) but never at or after the next slot; permanent ones (bad recipient,
        rejected message, missing config) abandon the edition at once, since retrying cannot help.

        keep_key: the send's outcome is unknown (Resend may have accepted it), so the retry keeps
        the stored idempotency key. Otherwise the key is cleared and the next attempt gets a new one.
        """
        logger.warning(f"Issue {claim.issue_id} failed ({error_kind}): {error}")
        attempts = delivery['attempts'] + 1
        cadence = self._cadence(issue)
        key_fields = {} if keep_key else {'idempotency_key': None}
        if force:
            # Manual sends are not retried.
            self.store.finish(
                claim, {'schedule_status': claim.previous_status, 'last_run_error': error},
                delivery['id'], {'status': 'failed', 'attempts': attempts, 'error': error, 'error_kind': error_kind,
                                 **key_fields},
                cadence=cadence,
            )
            return
        if error_kind == PERMANENT:
            self._abandon(claim, issue, delivery, error, error_kind, attempts, now)
            return
        if attempts >= MAX_RUN_ATTEMPTS:
            self._abandon(claim, issue, delivery, f"{error} (gave up after {MAX_RUN_ATTEMPTS} attempts)",
                          error_kind, attempts, now, one_shot_retries_tomorrow=True)
            return
        retry_at = now + max(retry_delay(attempts), timedelta(seconds=retry_after or 0))
        deadline = retry_deadline(issue, self._slot(delivery, now))
        if deadline is not None and retry_at >= deadline:
            # A late edition must not collide with the next one: stop retrying and wait for it.
            self._abandon(claim, issue, delivery, f"{error} (not retried: the next edition is due first)",
                          error_kind, attempts, now)
            return
        self.store.finish(
            claim, {'schedule_status': 'failed', 'next_run_at': retry_at, 'last_run_error': error},
            delivery['id'], {'status': 'failed', 'attempts': attempts, 'error': error, 'error_kind': error_kind,
                             'next_attempt_at': retry_at, **key_fields},
            cadence=cadence,
        )

    def _abandon(self, claim, issue, delivery, error, error_kind, attempts, now,
                 one_shot_retries_tomorrow=False) -> None:
        """Give up on this edition but keep the schedule alive: the issue moves to its next slot with
        the error recorded, and the owner is told once."""
        issue_fields = self._next_slot(issue, delivery, now)
        if one_shot_retries_tomorrow and issue_fields.get('auto_send') is False:
            # One-shot issue: try again tomorrow rather than silently turning it off.
            issue_fields = {'schedule_status': 'idle', 'next_run_at': now + MAX_BACKOFF}
        issue_fields['last_run_error'] = error
        self.store.finish(claim, issue_fields, delivery['id'], {
            'status': 'abandoned', 'attempts': attempts, 'error': error, 'error_kind': error_kind,
            'next_attempt_at': None,
        }, cadence=self._cadence(issue))
        self._notify_owner(delivery['id'])

    # ------------------------------------------------------------------
    # Owner notification (at most once per abandoned edition)
    # ------------------------------------------------------------------

    def _notify_pending_owners(self) -> None:
        """Send notices that a crash (or a failed send) left behind, a few per tick."""
        for delivery_id in self.store.unnotified_abandoned(limit=5):
            self._notify_owner(delivery_id)

    def _notify_owner(self, delivery_id) -> None:
        """Tell the issue's owner that an edition was abandoned. Whoever flips owner_notified_at
        sends. Only a *transient* send failure clears the flag so a later tick retries (the sweep
        waits out a cooldown, and the Resend idempotency key makes a duplicate harmless). A
        permanent failure (bad owner address, missing Resend config) or an unexpected error keeps
        the flag: retrying cannot help and would repeat every tick. Never raises: a notice must
        not break a run."""
        try:
            notice = self.store.claim_owner_notice(delivery_id)
            if notice is None:
                return
        except Exception:
            logger.exception(f"Owner notice for delivery {delivery_id} could not be claimed")
            return
        try:
            result = self._send_owner_notice(notice)
        except Exception:
            logger.exception(f"Owner notice for delivery {delivery_id} failed unexpectedly; not retrying")
            return
        if result.ok:
            return
        if result.error_kind != TRANSIENT:
            logger.error(f"Owner notice for delivery {delivery_id} cannot be sent, not retrying: {result.error}")
            return
        logger.warning(f"Owner notice for delivery {delivery_id} not sent, will retry: {result.error}")
        try:
            self.store.release_owner_notice(delivery_id)
        except Exception:
            logger.exception(f"Could not release the owner-notice flag for delivery {delivery_id}")

    def _send_owner_notice(self, notice: dict) -> SendResult:
        from services.email_service import EmailService
        return EmailService().send_owner_notice(
            to=notice['owner_email'],
            issue_title=notice.get('title'),
            period=notice.get('period_key'),
            error=notice.get('error'),
            next_run_at=_parse_ts(notice.get('next_run_at')),
            timezone_name=notice.get('schedule_timezone'),
            idempotency_key=f"owner-notice-{notice['id']}",
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
