# Scheduling Specification

## Purpose

Automatic, recurring PDF generation and delivery for issues that have `auto_send` enabled.
The schedule (what to send and when) lives on the `issues` row (see `data/migrations/2026_09_04_add_scheduling_fields.sql`);
each edition is a row in `issue_deliveries` (`supabase/migrations/20261005000000_issue_deliveries.sql`).
Cadence is per issue, not per user.

---

## Requirements

### Requirement: Scheduler Polling

The system SHALL run a background scheduler (APScheduler, started in the FastAPI lifespan) that polls
for due issues every 60 seconds and claims and processes up to 5 per tick, one at a time.

#### Scenario: Due issues are claimed without double-processing

- GIVEN multiple API workers and an issue with `auto_send=true`, `schedule_status='idle'`, and `next_run_at` in the past (or `schedule_status='failed'` past its retry time, or `processing` with `locked_at` older than `SCHEDULER_LOCK_TIMEOUT_MINUTES`, default 15)
- WHEN the scheduler polls
- THEN the issue is selected with `FOR UPDATE SKIP LOCKED`, marked `schedule_status='processing'` with `locked_at` and a new `claim_token` set, and only one worker processes it

#### Scenario: Lock timeout covers the worst-case run

- GIVEN `SCHEDULER_LOCK_TIMEOUT_MINUTES` is not longer than the worst-case run (`SCHEDULER_RSS_BUDGET_SECONDS`, default 300, + the 120s render timeout + 60s for email)
- WHEN the scheduler is constructed
- THEN it refuses to start (see "Scheduler startup failure is non-fatal but visible")

#### Scenario: Scheduler startup failure is non-fatal but visible

- GIVEN `SUPABASE_DATABASE_URL` is missing or invalid, or the lock timeout check fails
- WHEN the application starts
- THEN the API continues to serve requests without a scheduler, the failure is logged at CRITICAL, and `GET /health` returns `"status": "degraded"` with `"scheduler": "disabled: <reason>"` (so the deploy health check fails)

#### Scenario: pgbouncer query parameter is tolerated

- GIVEN `SUPABASE_DATABASE_URL` contains `pgbouncer=true`
- WHEN the scheduler builds its database engine
- THEN the unsupported parameter is stripped before connecting

---

### Requirement: Scheduled Run Processing

The system SHALL, for each due issue, fetch articles from the last `article_window_days` days (default 7),
generate a PDF using the issue's `format` and `remove_images`, and email it to `target_email`.

#### Scenario: Successful run

- GIVEN a due issue with recent articles
- WHEN it is processed and a PDF is generated
- THEN `last_run_at` is set, `next_run_at` is advanced, `schedule_status` returns to `idle`, and `last_run_error` is cleared

#### Scenario: No articles in window

- GIVEN a due issue with no articles in its window
- WHEN it is processed
- THEN no PDF is generated, `schedule_status` returns to `idle`, and `next_run_at` is advanced

#### Scenario: No recipient

- GIVEN a due issue whose `target_email` is missing or blank
- WHEN it is processed
- THEN no PDF is generated, the delivery is `abandoned` with `error_kind='permanent'` and error `config: no recipient email address is set`, and the issue advances to its next slot with that error in `last_run_error`

#### Scenario: Failed run is retried with backoff

- GIVEN PDF generation fails, or the email send fails with a `transient` error (see the email-delivery spec)
- WHEN the failure is recorded
- THEN the delivery is `failed` with `attempts` incremented, `error_kind='transient'` and `next_attempt_at` set 1h, 2h, 4h... (capped at 24h) ahead, or later if Resend's `Retry-After` is longer; the issue is `schedule_status='failed'` with `next_run_at` equal to that time and `last_run_error` holding the specific cause (prefixed `pdf:` or `email:`); the poll resumes the same delivery once due

#### Scenario: Permanent failure is not retried

- GIVEN the email send fails with a `permanent` error (for example an invalid recipient or a missing `RESEND_API_KEY`)
- WHEN the failure is recorded
- THEN the delivery is `abandoned` immediately with `error_kind='permanent'`, the issue advances to its next slot (a one-shot issue turns `auto_send` off), and `last_run_error` holds the cause

#### Scenario: Retries are exhausted

- GIVEN `SCHEDULER_MAX_ATTEMPTS` (default 5) failed attempts for one delivery
- WHEN the last failure is recorded
- THEN the delivery is `abandoned`, the issue returns to `idle` with `next_run_at` at the next cadence boundary, and `last_run_error` notes that it gave up

#### Scenario: Email failure after PDF generation retries the email only

- GIVEN a delivery whose PDF was generated but whose email failed
- WHEN it is retried
- THEN the delivery's stored `pdf_url` is sent without regenerating the PDF

---

### Requirement: Delivery Records

The system SHALL record each edition in `issue_deliveries` (`trigger` `scheduled` | `manual`, `period_key`, `scheduled_for`, `status` `pending` | `sending` | `sent` | `skipped` | `failed` | `abandoned`, `attempts`, `pdf_url`, `recipient`, `resend_message_id`, `error`). At most one scheduled delivery SHALL exist per `(issue_id, period_key)`, enforced by a unique index. Owners can read their issues' deliveries; only the scheduler writes them.

#### Scenario: At most one delivery per period

- GIVEN a scheduled delivery for issue A and period `2026-W41` that is `sent`, `skipped` or `abandoned`
- WHEN any worker processes issue A for period `2026-W41`
- THEN no new delivery is created, nothing is sent, and `next_run_at` advances to the next cadence boundary

#### Scenario: Period key comes from the slot

- GIVEN a daily delivery for the slot 2026-10-05 23:00 that is retried at 2026-10-06 00:30
- WHEN its period key is computed
- THEN it is `2026-10-05` (daily `YYYY-MM-DD`, weekly ISO `YYYY-Www`, monthly `YYYY-MM`, in `schedule_timezone`, from `next_run_at` when the delivery was opened)

#### Scenario: Re-enabled one-shot issue sends again

- GIVEN a `once` or `custom` issue that was sent before (so `auto_send` was turned off)
- WHEN the owner turns `auto_send` back on and the issue becomes due
- THEN a new delivery is created, because one-shot period keys are the slot timestamp (`once-<ISO time>`) and each enablement has a new slot

---

### Requirement: Claim Fencing

The system SHALL make every write after a claim conditional on the claim's `claim_token`, and SHALL commit a delivery as `sending` before calling Resend, storing the `Idempotency-Key` it uses (see Idempotent Sends in the email-delivery spec).

#### Scenario: Taken-over worker cannot overwrite state

- GIVEN worker 1 claimed an issue and is still running after `SCHEDULER_LOCK_TIMEOUT_MINUTES`
- AND worker 2 has reclaimed the issue with a new token
- WHEN worker 1 tries to mark the delivery `sending` or record its outcome
- THEN nothing is written, worker 1 logs the takeover and stops, and it sends no email

#### Scenario: Crash after the email was accepted

- GIVEN a delivery was committed as `sending` and the process died before it was marked `sent`
- WHEN the stale lock is reclaimed
- THEN the same delivery is resumed with its stored PDF and stored idempotency key, so Resend delivers the email once

#### Scenario: Unexpected error after sending keeps the key

- GIVEN an unexpected exception after the delivery was marked `sending`
- WHEN the failure is recorded
- THEN `attempts` is incremented (retries stay bounded) but the stored idempotency key is kept, so the retry reuses it

---

### Requirement: Rescheduling on Cadence Change

The system SHALL clear `next_run_at` and `last_run_error` (and reset `failed` to `idle`) whenever `auto_send`, `frequency`, `schedule_timezone`, `schedule_time_local`, `schedule_weekday` or `schedule_day_of_month` changes, and SHALL mark the issue's open `pending` or `failed` scheduled delivery `abandoned` with error `config: schedule changed`. A delivery that is already `sending` is left alone.

#### Scenario: Run in progress when the cadence changes

- GIVEN a run that loaded the issue's cadence and is still working when the owner changes it
- WHEN the run records its outcome
- THEN the delivery gets its real outcome (`sent` stays `sent`), but `next_run_at` stays NULL, `auto_send` is not changed, the issue is released as `idle`, and a `failed` outcome does not reopen an edition the trigger abandoned; the next poll schedules from the new cadence

#### Scenario: Newly enabled issue waits for the first cadence

- GIVEN an issue just switched to `auto_send=true`
- WHEN the next poll runs
- THEN `next_run_at` is initialised to one cadence interval ahead and nothing is sent yet; `once`/`custom` issues are due immediately

---

### Requirement: Next Run Computation

The system SHALL compute `next_run_at` from the issue's frequency in the issue's `schedule_timezone` (UTC if unknown), preserving local wall-clock time across DST: daily = +1 day, weekly = +7 days, monthly = +1 calendar month (day clamped to month end).

#### Scenario: One-shot frequencies disable auto-send

- GIVEN an issue with `frequency` of `once` or `custom`
- WHEN a scheduled run completes
- THEN `auto_send` is set to false and `next_run_at` is NULL

---

### Requirement: Send Now

The system SHALL expose `POST /issues/{issue_id}/send-now` to generate and email an issue immediately without changing its schedule. The caller MUST send a valid Supabase access token (`Authorization: Bearer <token>`) and own the issue (a `user_issues` row), and each issue is limited to one claim per `SEND_NOW_COOLDOWN_MINUTES` (default 10).

#### Scenario: Send now accepted

- GIVEN a signed-in user who owns an issue with a `target_email` that is not being processed and was not claimed within the cooldown
- WHEN the client sends `POST /issues/{issue_id}/send-now`
- THEN the API returns 202, work continues in the background as a `manual` delivery, and `next_run_at` and the scheduled delivery are unchanged (only `last_run_at` / `last_run_error` are updated); a failed manual send is not retried

#### Scenario: Send now takes over a stale lock

- GIVEN an issue stuck in `processing` with `locked_at` older than `SCHEDULER_LOCK_TIMEOUT_MINUTES`
- WHEN the client sends `POST /issues/{issue_id}/send-now`
- THEN the send proceeds, and afterwards `schedule_status` is `idle` (not `processing`), so the scheduler picks the issue up again

#### Scenario: Rejected send now

- GIVEN no or an invalid access token (401), the issue does not exist or belongs to another user (404, indistinguishable), it has no `target_email` (400), it is already `processing` (409), or its `locked_at` is within `SEND_NOW_COOLDOWN_MINUTES` (429 with `Retry-After`)
- WHEN the client sends `POST /issues/{issue_id}/send-now`
- THEN the corresponding error is returned and nothing is started
