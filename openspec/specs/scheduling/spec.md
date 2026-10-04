# Scheduling Specification

## Purpose

Automatic, recurring PDF generation and delivery for issues that have `auto_send` enabled.
Scheduling state lives on the `issues` row (see `data/migrations/2026_09_04_add_scheduling_fields.sql`);
cadence is per issue, not per user.

---

## Requirements

### Requirement: Scheduler Polling

The system SHALL run a background scheduler (APScheduler, started in the FastAPI lifespan) that polls
for due issues every 60 seconds and processes them in batches of up to 5.

#### Scenario: Due issues are claimed without double-processing

- GIVEN multiple API workers and an issue with `auto_send=true`, `schedule_status='idle'`, and `next_run_at` in the past (or `schedule_status='failed'` past its retry time, or `processing` with `locked_at` older than `SCHEDULER_LOCK_TIMEOUT_MINUTES`, default 15)
- WHEN the scheduler polls
- THEN the issue is selected with `FOR UPDATE SKIP LOCKED`, marked `schedule_status='processing'` with `locked_at` set, and only one worker processes it

#### Scenario: Scheduler startup failure is non-fatal

- GIVEN `SUPABASE_DATABASE_URL` is missing or invalid
- WHEN the application starts
- THEN the failure is logged and the API continues to serve requests without a scheduler

#### Scenario: pgbouncer query parameter is tolerated

- GIVEN `SUPABASE_DATABASE_URL` contains `pgbouncer=true`
- WHEN the scheduler builds its database engine
- THEN the unsupported parameter is stripped before connecting

---

### Requirement: Scheduled Run Processing

The system SHALL, for each due issue, fetch articles from the last `article_window_days` days (default 7),
generate a PDF using the issue's `format` and `remove_images`, and email it to `target_email` if set.

#### Scenario: Successful run

- GIVEN a due issue with recent articles
- WHEN it is processed and a PDF is generated
- THEN `last_run_at` is set, `next_run_at` is advanced, `schedule_status` returns to `idle`, and `last_run_error` is cleared

#### Scenario: No articles in window

- GIVEN a due issue with no articles in its window
- WHEN it is processed
- THEN no PDF is generated, `schedule_status` returns to `idle`, and `next_run_at` is advanced

#### Scenario: Failed run is retried with backoff

- GIVEN PDF generation or email delivery fails for a due issue
- WHEN the failure is recorded
- THEN `schedule_status='failed'`, `last_run_error` holds the message (prefixed `pdf:` or `email:`), `run_attempts` is incremented, and `next_run_at` is set 1h, 2h, 4h... (capped at 24h) ahead; the poll picks it up again once due

#### Scenario: Retries are exhausted

- GIVEN `SCHEDULER_MAX_ATTEMPTS` (default 5) consecutive failures
- WHEN the last failure is recorded
- THEN the issue returns to `idle`, `next_run_at` moves to the next cadence boundary, `run_attempts` resets, and `last_run_error` notes that it gave up

#### Scenario: Email failure after PDF generation retries the email only

- GIVEN a PDF was generated but the email failed
- WHEN the failure is recorded
- THEN `pending_pdf_url` and `pending_period` are stored, and the retry within the same period resends that URL without regenerating the PDF

#### Scenario: At most one delivery per period

- GIVEN a recurring issue (`daily`, `weekly` or `monthly`) whose `last_sent_period` equals the current period key (daily `YYYY-MM-DD`, weekly ISO `YYYY-Www`, monthly `YYYY-MM`, in `schedule_timezone`)
- WHEN the issue is processed by the scheduler
- THEN nothing is sent and `next_run_at` is advanced

#### Scenario: Re-enabled one-shot issue sends again

- GIVEN a `once` or `custom` issue that was sent before (so `last_sent_period='once'` and `auto_send` was turned off)
- WHEN the owner turns `auto_send` back on and the issue becomes due
- THEN the period check does not apply and the issue is generated and sent; one-shot issues rely on `auto_send` turning off after a successful send

#### Scenario: Newly enabled issue waits for the first cadence

- GIVEN an issue just switched to `auto_send=true` (a database trigger clears `next_run_at`, `run_attempts` and pending state whenever `auto_send` changes)
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

### Requirement: Manual Trigger

The system SHALL expose `POST /pdf/trigger-scheduled/{issue_id}` to run the scheduler's processing logic for one issue on demand (testing aid).

#### Scenario: Manual trigger runs full flow

- GIVEN an existing issue
- WHEN the client sends `POST /pdf/trigger-scheduled/{issue_id}`
- THEN PDF generation and email delivery run once and `{"success": true}` is returned

---

### Requirement: Send Now

The system SHALL expose `POST /issues/{issue_id}/send-now` to generate and email an issue immediately without changing its schedule.

#### Scenario: Send now accepted

- GIVEN an issue with a `target_email` that is not being processed
- WHEN the client sends `POST /issues/{issue_id}/send-now`
- THEN the API returns 202, work continues in the background, and `next_run_at`, `last_sent_period` and retry state are unchanged (only `last_run_at` / `last_run_error` are updated)

#### Scenario: Send now takes over a stale lock

- GIVEN an issue stuck in `processing` with `locked_at` older than `SCHEDULER_LOCK_TIMEOUT_MINUTES`
- WHEN the client sends `POST /issues/{issue_id}/send-now`
- THEN the send proceeds, and afterwards `schedule_status` is `idle` (not `processing`), so the scheduler picks the issue up again

#### Scenario: Rejected send now

- GIVEN the issue does not exist (404), has no `target_email` (400), or is already `processing` (409)
- WHEN the client sends `POST /issues/{issue_id}/send-now`
- THEN the corresponding error is returned and nothing is started
