# Change Proposal: Production-Ready Scheduled Delivery

GitHub: #17 (parent), #21 (stale locks / duplicate sends), #22 (swallowed email failures), #23 (failed runs never retried).
Builds on: `openspec/changes/scheduled-delivery-hardening` (PR #5), which must be rebased and merged first.
Supersedes: the unfinished verification items in `openspec/changes/email-automation`.

## Why

Scheduled email delivery works on the happy path, but it is not safe to offer to other users:

- A failed run is never retried and an email failure is recorded as success, so a subscriber can silently stop receiving papers (#22, #23).
- A crash mid-run leaves the issue stuck in `processing` forever, and a recovered run can email the same edition twice (#21).
- PR #5 fixes most of this, but it computes the next run from "now" (a late retry permanently moves the delivery slot), lets a daily issue's retries run into the next day, keeps no delivery history, and does not tell permanent errors from transient ones.
- The `schedule_weekday`, `schedule_day_of_month` and `schedule_time_local` columns exist in the database, but nothing uses them. `schedule_timezone` is always UTC.
- Any signed-in user can point `target_email` at any address and, through direct Supabase writes, make it send repeatedly. `POST /issues/{id}/send-now` and `POST /pdf/trigger-scheduled/{id}` do not check who is calling.
- Editions use a fixed lookback window, so a daily issue with the default 7-day window repeats the same articles every day.

## What Changes

Owner decisions (2026-10-03) are marked **[decision]**.

1. **Delivery records [decision].** A new `issue_deliveries` table with one row per edition. `UNIQUE (issue_id, period_key)` for scheduled editions enforces at most one delivery per period in the database. It replaces PR #5's `last_sent_period`, `pending_pdf_url`, `pending_period` and `run_attempts` columns before that migration ships.
2. **Crash safety (#21).** Each claim gets a token, and every final write is conditional on that token. The delivery row is marked `sending` before Resend is called, and every send carries a Resend `Idempotency-Key` derived from the delivery.
3. **Error reporting and classification (#22).** `EmailService` returns a structured result. Failures are classified as `transient` (429, 5xx, timeout) or `permanent` (invalid or unverified recipient, missing configuration, unverified sending domain). Only transient failures are retried.
4. **Retries bounded by the period (#23).** Exponential backoff (1h, 2h, 4h, 8h, capped at 24h, at most 5 attempts) that never runs past the next delivery slot.
5. **Give-up handling [decision].** When an edition is abandoned, the issue keeps its schedule for the next period, the UI shows the error, and the owner gets one "this edition failed" email.
6. **Anchored, fine-grained schedule.** The next run is computed from the configured slot (local time, weekday or day of month, IANA timezone), never from processing time. Changing any cadence field reschedules the issue.
7. **Articles since the last delivery [decision].** An edition contains articles published since the previous delivered edition, capped by `article_window_days`.
8. **Verified recipients [decision].** The account email is verified automatically. Any other `target_email` must be confirmed through a link before scheduled or manual sends go to it.
9. **Unsubscribe.** Every delivery email has a one-click unsubscribe link and `List-Unsubscribe` / `List-Unsubscribe-Post` headers.
10. **Access control.** Scheduler-owned columns cannot be written by `anon` or `authenticated`. Send now requires an authenticated owner. `POST /pdf/trigger-scheduled/{id}` is removed.
11. **UI.** Schedule controls (weekday, day of month, time, auto-detected timezone), a status panel driven by server state (next delivery, last delivery, last error), delivery history, and the verification state of the recipient.
12. **Testing.** Property tests for scheduling math, state-machine tests, integration tests against local Supabase (concurrency, stale-lock takeover, triggers, column privileges), email contract tests, vitest for the UI, and a staging run with Resend test addresses.

## Scope

In scope: `services/scheduler.py`, `services/email_service.py`, `routers/issues.py`, `routers/pdf.py`, a new migration under `newsletter2paper/supabase/migrations/`, `ui/app/components/ConfigureNewspaper.js`, `ui/contexts/useNewsletterConfig.js`, new UI routes for send-now, verify-email and unsubscribe, and the spec deltas in this change.

Out of scope (follow-up issues):

- Resend webhooks: pause `auto_send` on a hard bounce or complaint.
- Richer email body (table of contents, attaching small PDFs).
- Scheduler heartbeat and alerting, PDF storage retention, a separate worker container, pgmq.
- Optional "no new articles this edition" email.

## Success Criteria

- An issue is emailed at most once per period, including when the process is killed at any point in a run (verified by integration tests and a manual kill test).
- Every failed send leaves a specific, user-readable error on the delivery and on the issue. Transient failures are delivered later in the same period, permanent ones are not retried, and the owner is notified once when an edition is abandoned.
- Delivery happens at the configured local time and weekday or day of month, stays there after late retries and DST changes, and moves when the owner changes the schedule.
- Consecutive editions never repeat an article.
- Scheduled sends go only to verified addresses, and no client can trigger a send for an issue it does not own.
