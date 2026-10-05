# Scheduling Spec Delta: Production-Ready Scheduled Delivery

Relative to `openspec/specs/scheduling/spec.md` as introduced by PR #5 (`scheduled-delivery-hardening`).

## ADDED Requirements

### Requirement: Delivery Records

The system SHALL record each edition in `issue_deliveries`, with `trigger` (`scheduled` | `manual`), `period_key`, `scheduled_for`, `status` (`pending` | `sending` | `sent` | `skipped` | `failed` | `abandoned`), `attempts`, article window, recipient, Resend message id and error. At most one scheduled delivery SHALL exist per `(issue_id, period_key)`, and this is enforced by a unique index.

#### Scenario: Second scheduled delivery for the same period is rejected

- GIVEN a scheduled delivery with status `sent` for issue A and period `2026-W41`
- WHEN any worker attempts to start a scheduled delivery for issue A and period `2026-W41`
- THEN no new delivery is created, no email is sent, and the issue's `next_run_at` advances to the next slot

#### Scenario: Owner reads delivery history

- GIVEN an authenticated owner of an issue
- WHEN they request `GET /issues/{id}/deliveries`
- THEN the most recent deliveries are returned newest first, and non-owners receive 403

---

### Requirement: Claim Fencing

The system SHALL assign a new `claim_token` on every claim and SHALL make every subsequent write to the issue conditional on that token.

#### Scenario: Taken-over worker cannot overwrite state

- GIVEN worker 1 claimed an issue and is still running after `SCHEDULER_LOCK_TIMEOUT_MINUTES`
- AND worker 2 has reclaimed the issue with a new token
- WHEN worker 1 attempts to finalise
- THEN its update affects no rows, it logs the takeover, and it does not send email

#### Scenario: Crash after the email was accepted

- GIVEN a delivery was marked `sending` and Resend accepted the email
- AND the process died before the delivery was marked `sent`
- WHEN the issue is reclaimed
- THEN the send is retried with the same `Idempotency-Key`, the recipient receives exactly one email, and the delivery becomes `sent`

---

### Requirement: Retry Policy

The system SHALL retry transient failures with exponential backoff (1h, 2h, 4h, 8h, … capped at 24h) up to `SCHEDULER_MAX_ATTEMPTS` (default 5), and SHALL NOT schedule a retry at or after the issue's next slot.

#### Scenario: Transient failure is retried within the period

- GIVEN a weekly issue whose email send fails with HTTP 503
- WHEN the failure is recorded
- THEN the delivery is `failed` with `error_kind='transient'`, `attempts` is incremented, and `issues.next_run_at` equals the delivery's `next_attempt_at`

#### Scenario: Retry would cross into the next period

- GIVEN a daily issue at 09:00 whose 4th attempt fails at 23:30, with an 8h backoff
- WHEN the failure is recorded
- THEN the delivery becomes `abandoned` and the issue's `next_run_at` is the next day's 09:00 slot

#### Scenario: Permanent failure is not retried

- GIVEN an email send fails with `error_kind='permanent'` (for example an invalid recipient or a missing `RESEND_API_KEY`)
- WHEN the failure is recorded
- THEN the delivery becomes `abandoned` immediately and the issue advances to its next slot

#### Scenario: Email-only retry reuses the PDF

- GIVEN a delivery whose PDF was generated but whose email failed transiently
- WHEN it is retried
- THEN the stored `pdf_url` is sent without regenerating the PDF

---

### Requirement: Owner Failure Notification

The system SHALL email the issue owner's account address once when a scheduled delivery is abandoned, keep the issue's schedule active, and expose the error through `last_run_error`.

#### Scenario: Edition abandoned

- GIVEN a scheduled delivery becomes `abandoned`
- WHEN the abandonment is recorded
- THEN one notification is sent to the owner's account email, stating the issue title, period and a plain-language reason
- AND `owner_notified_at` is set
- AND `auto_send` remains true

#### Scenario: Notification is not repeated

- GIVEN `owner_notified_at` is already set for a delivery
- WHEN the delivery is processed again (for example after a crash)
- THEN no further notification is sent

#### Scenario: A lost or failed notice is sent later

- GIVEN a delivery is `abandoned` with `owner_notified_at` NULL (the process died, or the notice email failed)
- WHEN the scheduler next polls
- THEN the notice is sent (recent abandoned editions only) and `owner_notified_at` is set; if sending fails the flag is cleared again so a later poll retries
- AND the notice carries a Resend idempotency key, so a repeat inside 24h is not delivered twice

#### Scenario: Abandonment caused by a schedule change does not notify

- GIVEN an open delivery is abandoned because the owner changed the cadence
- WHEN the trigger runs
- THEN no notification is sent

---

### Requirement: Edition Article Selection

The system SHALL fill a scheduled edition with articles published after the `articles_until` of the issue's most recent `sent` delivery (scheduled or manual), but no earlier than `article_window_days` before generation.

#### Scenario: Consecutive editions do not overlap

- GIVEN a daily issue with `article_window_days=7` and a delivery sent yesterday with `articles_until` = yesterday 09:00
- WHEN today's edition is generated at 09:00
- THEN only articles published after yesterday 09:00 are included

#### Scenario: First edition uses the full window

- GIVEN an issue with no sent deliveries
- WHEN its first edition is generated
- THEN articles from the last `article_window_days` days are included

#### Scenario: No new articles

- GIVEN no articles were published in the computed window
- WHEN the edition is processed
- THEN the delivery is `skipped`, no email is sent, and the issue advances to its next slot

---

### Requirement: Scheduler-Owned Columns Are Protected

The system SHALL NOT allow the `anon` or `authenticated` roles to update `next_run_at`, `schedule_status`, `locked_at`, `claim_token`, `last_run_at`, `last_run_error`, `target_email_verified_at` or `unsubscribe_token`, and SHALL NOT allow those roles to write `issue_deliveries`.

#### Scenario: Browser tries to force a send

- GIVEN a signed-in user using the Supabase client directly
- WHEN they update `next_run_at` on their own issue
- THEN the update is rejected with a permission error

## MODIFIED Requirements

### Requirement: Next Run Computation

The system SHALL compute delivery slots from the issue's `schedule_time_local` (default `09:00`), `schedule_weekday` (weekly; 0 = Monday), `schedule_day_of_month` (monthly; clamped to the month's last day) and `schedule_timezone` (IANA; UTC if invalid). The next slot SHALL be anchored to the previous slot, not to processing time, and missed slots SHALL NOT be replayed.

#### Scenario: Late retry does not move the slot

- GIVEN a weekly issue on Friday at 09:00 America/New_York whose delivery succeeded on the third attempt at 16:00
- WHEN `next_run_at` is computed
- THEN it is the following Friday at 09:00 America/New_York

#### Scenario: Local time is kept across DST

- GIVEN a daily issue at 09:00 Europe/London
- WHEN the slot after the last Saturday of October is computed
- THEN it is Sunday 09:00 local time (09:00 UTC rather than 08:00 UTC)

#### Scenario: Slot falls in a DST gap

- GIVEN a daily issue at 02:30 America/New_York
- WHEN the spring-forward day's slot is computed
- THEN it is 03:00 local time on that day

#### Scenario: Monthly day clamps to month end

- GIVEN a monthly issue with `schedule_day_of_month=31`
- WHEN the February slot is computed
- THEN it is February 28 (or 29 in a leap year) at the configured local time

#### Scenario: Downtime does not replay missed editions

- GIVEN a daily issue whose scheduler was down for three days
- WHEN the scheduler resumes
- THEN at most one catch-up edition is sent, and `next_run_at` is the next future slot

#### Scenario: One-shot frequencies disable auto-send

- GIVEN an issue with `frequency` of `once` or `custom`
- WHEN a scheduled run completes
- THEN `auto_send` is set to false and `next_run_at` is NULL

---

### Requirement: Period Key

The system SHALL derive `period_key` from the delivery's `scheduled_for` slot in `schedule_timezone`: daily `YYYY-MM-DD`, weekly ISO `YYYY-Www`, monthly `YYYY-MM`.

#### Scenario: Retry processed after midnight keeps its period

- GIVEN a daily delivery scheduled for 2026-10-05 23:00 that is retried at 2026-10-06 00:30
- WHEN its period key is computed
- THEN it is `2026-10-05`

---

### Requirement: Rescheduling on Cadence Change

The system SHALL reset `next_run_at` whenever `auto_send`, `frequency`, `schedule_timezone`, `schedule_time_local`, `schedule_weekday` or `schedule_day_of_month` changes. The next poll SHALL set it to the first slot after now, and SHALL NOT send immediately.

#### Scenario: Switching weekly to daily

- GIVEN a weekly issue whose `next_run_at` is six days away
- WHEN the owner changes `frequency` to `daily`
- THEN after the next poll `next_run_at` is the next daily slot

#### Scenario: Newly enabled issue waits for its first slot

- GIVEN an issue just switched to `auto_send=true`
- WHEN the next poll runs
- THEN `next_run_at` is the first slot after now and nothing is sent

---

### Requirement: Send Now

The system SHALL expose `POST /issues/{issue_id}/send-now` to the authenticated owner of the issue. It SHALL generate and email the issue immediately as a `manual` delivery, without changing `next_run_at`.

#### Scenario: Send now accepted

- GIVEN the owner of an issue with a verified `target_email` that is not being processed
- WHEN they send `POST /issues/{issue_id}/send-now`
- THEN the API returns 202, a `manual` delivery is created, and `next_run_at` is unchanged

#### Scenario: Send now rejected

- GIVEN any of the following:
  - no or an invalid token (401);
  - a caller who is not the owner (403);
  - a missing issue (404);
  - no `target_email` (400);
  - a run already in progress (409);
  - an unverified recipient (412)
- WHEN `POST /issues/{issue_id}/send-now` is called
- THEN the corresponding status is returned and nothing is started

## REMOVED Requirements

### Requirement: Manual Trigger

`POST /pdf/trigger-scheduled/{issue_id}` is removed. It was an unauthenticated testing aid that bypassed idempotency; Send now replaces it.
