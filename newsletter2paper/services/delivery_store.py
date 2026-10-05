"""Postgres access for the scheduler: claiming issues and recording deliveries.

Every write after a claim is fenced on `issues.claim_token`. A worker whose claim was taken
over (its run outlived SCHEDULER_LOCK_TIMEOUT_MINUTES and another worker reclaimed the issue)
gets ClaimLost instead of overwriting the newer run's state.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy import text

# Delivery statuses that close an edition; anything else is resumed by the next run.
CLOSED_STATUSES = {'sent', 'skipped', 'abandoned'}

_ISSUE_COLUMNS = {'schedule_status', 'next_run_at', 'last_run_at', 'last_run_error', 'auto_send'}
# Columns the cadence trigger watches. A run's next_run_at / auto_send are only valid for the
# cadence it loaded; see DeliveryStore.finish.
CADENCE_COLUMNS = {
    'auto_send': 'boolean', 'frequency': 'text', 'schedule_timezone': 'text',
    'schedule_time_local': 'text', 'schedule_weekday': 'integer', 'schedule_day_of_month': 'integer',
}
_DELIVERY_COLUMNS = {'status', 'attempts', 'next_attempt_at', 'error', 'error_kind', 'idempotency_key', 'pdf_url', 'recipient',
                     'resend_message_id', 'sent_at'}


class ClaimLost(Exception):
    """Another worker reclaimed the issue; the current run must stop without writing."""


class SendNowCooldown(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"retry after {retry_after}s")
        self.retry_after = retry_after


@dataclass(frozen=True)
class Claim:
    issue_id: str
    token: str
    # schedule_status to restore after a manual send; scheduled runs set their own.
    previous_status: str = 'idle'


class DeliveryStore:
    def __init__(self, engine):
        self.engine = engine

    # ------------------------------------------------------------------
    # Claiming
    # ------------------------------------------------------------------

    def initialize_unscheduled(self, first_run: Callable[[dict], datetime]) -> list:
        """Give auto_send issues without next_run_at their first run time; returns (id, next_at) pairs.

        `first_run` receives the issue's schedule columns (frequency, timezone, local time, weekday,
        day of month) and returns its first slot."""
        initialised = []
        with self.engine.begin() as conn:
            rows = conn.execute(text(
                """
                SELECT id, frequency, schedule_timezone, schedule_time_local, schedule_weekday, schedule_day_of_month
                FROM public.issues
                WHERE auto_send = true AND next_run_at IS NULL AND schedule_status = 'idle'
                FOR UPDATE SKIP LOCKED
                """
            )).mappings().fetchall()
            for row in rows:
                next_at = first_run(dict(row))
                conn.execute(
                    text("UPDATE public.issues SET next_run_at = :next_at, updated_at = now() WHERE id = :id"),
                    {"id": row["id"], "next_at": next_at},
                )
                initialised.append((row["id"], next_at))
        return initialised

    def claim_next_due(self, lock_timeout_minutes: int) -> Optional[Claim]:
        """Claim one due issue (idle, retryable failure, or stale lock) with a fresh token."""
        token = str(uuid.uuid4())
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    WITH due AS (
                      SELECT id FROM public.issues
                      WHERE auto_send = true
                        AND next_run_at <= now()
                        AND (
                          schedule_status IN ('idle', 'failed')
                          OR (schedule_status = 'processing'
                              AND locked_at < now() - make_interval(mins => :lock_timeout))
                        )
                      ORDER BY next_run_at
                      FOR UPDATE SKIP LOCKED
                      LIMIT 1
                    )
                    UPDATE public.issues AS i
                    SET schedule_status = 'processing', locked_at = now(), claim_token = CAST(:token AS uuid)
                    FROM due WHERE i.id = due.id
                    RETURNING i.id
                    """
                ),
                {"lock_timeout": lock_timeout_minutes, "token": token},
            ).fetchone()
        return Claim(str(row[0]), token) if row else None

    def claim_for_send_now(self, issue_id: str, lock_timeout_minutes: int, cooldown_minutes: int) -> Optional[Claim]:
        """Lock one issue for a manual send. None if a run holds a fresh lock; SendNowCooldown if
        the issue was claimed (manually or by the poll) within the cooldown."""
        token = str(uuid.uuid4())
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
                if prev == 'processing' and age < timedelta(minutes=lock_timeout_minutes):
                    return None
                cooldown = timedelta(minutes=cooldown_minutes)
                if age < cooldown:
                    raise SendNowCooldown(int((cooldown - age).total_seconds()) + 1)
            conn.execute(
                text(
                    "UPDATE public.issues SET schedule_status = 'processing', locked_at = now(), "
                    "claim_token = CAST(:token AS uuid) WHERE id = :id"
                ),
                {"id": str(issue_id), "token": token},
            )
        # A stale 'processing' lock belongs to a crashed run; restoring it would leave the row
        # stuck again, so hand it back to the poll as 'idle' (next_run_at is untouched).
        return Claim(str(issue_id), token, 'idle' if prev == 'processing' else prev)

    # ------------------------------------------------------------------
    # Deliveries
    # ------------------------------------------------------------------

    def open_scheduled_delivery(self, claim: Claim, scheduled_for: datetime, period_key: str) -> dict:
        """Return the issue's open scheduled delivery, or create one for `period_key`.

        If that period already has a delivery (the unique index rejects a second one), it is
        returned as is; a closed status means the edition was already handled.
        """
        with self.engine.begin() as conn:
            self._check_claim(conn, claim)
            row = conn.execute(
                text(
                    """
                    SELECT * FROM public.issue_deliveries
                    WHERE issue_id = :issue_id AND trigger = 'scheduled'
                      AND status IN ('pending', 'failed', 'sending')
                    ORDER BY created_at DESC LIMIT 1
                    """
                ),
                {"issue_id": claim.issue_id},
            ).mappings().fetchone()
            if row:
                return dict(row)
            row = conn.execute(
                text(
                    """
                    INSERT INTO public.issue_deliveries (issue_id, trigger, period_key, scheduled_for)
                    VALUES (:issue_id, 'scheduled', :period_key, :scheduled_for)
                    ON CONFLICT (issue_id, period_key) WHERE trigger = 'scheduled' DO NOTHING
                    RETURNING *
                    """
                ),
                {"issue_id": claim.issue_id, "period_key": period_key, "scheduled_for": scheduled_for},
            ).mappings().fetchone()
            if row:
                return dict(row)
            return dict(conn.execute(
                text(
                    "SELECT * FROM public.issue_deliveries "
                    "WHERE issue_id = :issue_id AND trigger = 'scheduled' AND period_key = :period_key"
                ),
                {"issue_id": claim.issue_id, "period_key": period_key},
            ).mappings().one())

    def create_manual_delivery(self, claim: Claim) -> dict:
        with self.engine.begin() as conn:
            self._check_claim(conn, claim)
            return dict(conn.execute(
                text(
                    "INSERT INTO public.issue_deliveries (issue_id, trigger, scheduled_for) "
                    "VALUES (:issue_id, 'manual', now()) RETURNING *"
                ),
                {"issue_id": claim.issue_id},
            ).mappings().one())

    def mark_sending(self, claim: Claim, delivery_id, pdf_url: str, recipient: str, idempotency_key: str) -> None:
        """Commit that the email is about to be sent, with the idempotency key it will use. A run
        that finds this status after a crash resends with the same key instead of risking a
        second email."""
        with self.engine.begin() as conn:
            self._check_claim(conn, claim)
            conn.execute(
                text(
                    "UPDATE public.issue_deliveries SET status = 'sending', pdf_url = :pdf_url, "
                    "recipient = :recipient, idempotency_key = :key, updated_at = now() WHERE id = :id"
                ),
                {"id": delivery_id, "pdf_url": pdf_url, "recipient": recipient, "key": idempotency_key},
            )

    def finish(self, claim: Claim, issue: dict, delivery_id=None, delivery: Optional[dict] = None,
               cadence: Optional[dict] = None) -> None:
        """Write the run's outcome to the issue and (optionally) its delivery in one transaction.

        The issue update is conditional on the claim token; if another worker has taken over,
        nothing is written and ClaimLost is raised. The issue is updated first because changing
        auto_send fires the cadence trigger, which would otherwise reopen-and-abandon the delivery.

        `cadence` is the issue's cadence as the run loaded it. If the owner changed it mid-run,
        the trigger has already cleared next_run_at and abandoned the open edition; the run then
        leaves next_run_at NULL, keeps auto_send, releases the issue as 'idle' and does not revive
        the abandoned edition as 'failed', so the next poll schedules from the new cadence.
        """
        _check_columns(issue, _ISSUE_COLUMNS)
        _check_columns(delivery or {}, _DELIVERY_COLUMNS)
        _check_columns(cadence or {}, set(CADENCE_COLUMNS))
        params = {**issue, "_id": claim.issue_id, "_token": claim.token}
        exprs = {}
        if cadence:
            unchanged = ' AND '.join(
                f"{col}::text IS NOT DISTINCT FROM CAST(CAST(:_c_{col} AS {typ}) AS text)"
                for col, typ in CADENCE_COLUMNS.items() if col in cadence
            )
            params.update({f"_c_{col}": val for col, val in cadence.items()})
            exprs = {
                'next_run_at': f"CASE WHEN {unchanged} THEN CAST(:next_run_at AS timestamptz) END",
                'auto_send': f"CASE WHEN {unchanged} THEN CAST(:auto_send AS boolean) ELSE auto_send END",
                'schedule_status': f"CASE WHEN {unchanged} THEN CAST(:schedule_status AS text) ELSE 'idle' END",
            }
        delivery_exprs = {
            # Only the cadence trigger abandons an edition mid-run; a retry must not reopen it.
            'status': "CASE WHEN status = 'abandoned' AND CAST(:status AS text) = 'failed' THEN status ELSE :status END",
            'next_attempt_at': "CASE WHEN status = 'abandoned' THEN NULL ELSE CAST(:next_attempt_at AS timestamptz) END",
        }
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    f"UPDATE public.issues SET {_assignments(issue, exprs)}updated_at = now() "
                    "WHERE id = :_id AND claim_token = CAST(:_token AS uuid)"
                ),
                params,
            )
            if result.rowcount == 0:
                raise ClaimLost(claim.issue_id)
            if delivery_id is not None and delivery:
                conn.execute(
                    text(
                        f"UPDATE public.issue_deliveries SET {_assignments(delivery, delivery_exprs)}"
                        "updated_at = now() WHERE id = :_id"
                    ),
                    {**delivery, "_id": delivery_id},
                )

    # ------------------------------------------------------------------
    # Owner notification
    # ------------------------------------------------------------------

    # An edition abandoned because the owner changed the schedule is not a failure to report.
    _NOTIFIABLE = (
        "d.trigger = 'scheduled' AND d.status = 'abandoned' AND d.owner_notified_at IS NULL "
        "AND d.error NOT LIKE 'config: schedule changed%'"
    )

    def claim_owner_notice(self, delivery_id) -> Optional[dict]:
        """Atomically mark an abandoned edition as notified and return what the notice needs, or
        None if it was already notified, is not notifiable, or the issue has no owner account.
        Only the caller that gets a row sends the email."""
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    UPDATE public.issue_deliveries AS d SET owner_notified_at = now()
                    FROM public.issues AS i
                    WHERE d.id = :id AND d.issue_id = i.id AND {self._NOTIFIABLE}
                    RETURNING d.id, d.period_key, d.error, i.title, i.next_run_at, i.schedule_timezone,
                      (SELECT u.email FROM public.user_issues ui JOIN auth.users u ON u.id = ui.user_id
                       WHERE ui.issue_id = i.id ORDER BY ui.created_at LIMIT 1) AS owner_email
                    """
                ),
                {"id": delivery_id},
            ).mappings().fetchone()
        if row is None:
            return None
        notice = dict(row)
        # No owner account (an unowned guest issue): nothing to send; the flag stays set.
        return notice if notice.get('owner_email') else None

    def release_owner_notice(self, delivery_id) -> None:
        """Undo claim_owner_notice after a failed send so a later tick retries it."""
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE public.issue_deliveries SET owner_notified_at = NULL WHERE id = :id"),
                {"id": delivery_id},
            )

    def unnotified_abandoned(self, limit: int = 5, within_days: int = 7) -> list:
        """Recently abandoned editions whose notice was never sent (a crash, or a failed send)."""
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT d.id FROM public.issue_deliveries d
                    WHERE {self._NOTIFIABLE} AND d.updated_at > now() - make_interval(days => :days)
                    ORDER BY d.updated_at LIMIT :limit
                    """
                ),
                {"limit": limit, "days": within_days},
            ).fetchall()
        return [r[0] for r in rows]

    def _check_claim(self, conn, claim: Claim) -> None:
        # FOR UPDATE holds the row until commit, so a takeover cannot slip in between the check
        # and the delivery write that follows it.
        row = conn.execute(
            text("SELECT 1 FROM public.issues WHERE id = :id AND claim_token = CAST(:token AS uuid) FOR UPDATE"),
            {"id": claim.issue_id, "token": claim.token},
        ).fetchone()
        if not row:
            raise ClaimLost(claim.issue_id)


def _check_columns(fields: dict, allowed: set) -> None:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unexpected columns: {sorted(unknown)}")


def _assignments(fields: dict, exprs: Optional[dict] = None) -> str:
    """SET list for `fields`, using exprs[col] instead of the plain bind where one is given.

    Expressions on the right-hand side see the row as it was before this UPDATE."""
    exprs = exprs or {}
    return ''.join(f"{col} = {exprs.get(col, ':' + col)}, " for col in fields)
