# Tasks: Production-Ready Scheduled Delivery

GitHub issue for each group in brackets. Parent: #17.

## 0. Land PR #5 (prerequisite)

- [x] Rebase `feature/scheduler-hardening` onto `main` (CI's async test failures are fixed by `asyncio_mode = auto` on `main`)
- [x] Move `data/migrations/2026_10_04_scheduler_hardening.sql` to `newsletter2paper/supabase/migrations/` (with `data/migrations` symlink per repo convention)
- [x] Remove `run_attempts`, `last_sent_period`, `pending_pdf_url`, `pending_period` (replaced by `issue_deliveries`, §1). Done as a `DROP COLUMN IF EXISTS` in `20261005000000_issue_deliveries.sql` instead, so PR #5's code keeps working until this lands
- [x] Use `request.app.state.scheduler` in send-now instead of constructing `SchedulerService()` per request
- [x] Merge PR #5

## 1. Delivery records and schema

- [x] Migration: `issue_deliveries` table, partial unique index `(issue_id, period_key) WHERE trigger='scheduled'`, history index, RLS select-for-owner
- [x] Migration: `issues.claim_token`, `target_email_verified_at`, `unsubscribe_token`; `email_verifications` table (`20261010000000_recipient_verification.sql`; `claim_token` shipped earlier)
- [x] Migration: `reset_schedule_on_cadence_change` trigger (replaces PR #5 auto_send-only trigger)
- [x] Migration: `reset_verification_on_email_change` trigger; backfill verified for account-email recipients (one trigger, `enforce_recipient_verification`, also refuses `auto_send` for unverified recipients from browser roles)
- [x] Migration: `REVOKE UPDATE` on scheduler-owned and verification columns from `anon`, `authenticated`
- [x] pgTAP tests for triggers, unique index, column privileges, delivery RLS (plain-SQL tests in `supabase/tests/delivery_schema.sql`, run by `test-db-migrations.yml`, like the other DB tests)

## 2. Scheduling math

- [x] `services/scheduling.py`: `slot_after`, `period_key`, `retry_deadline`, `next_slot_after_delivery` (the untracked `scheduling_utils.py` was never committed)
- [x] Honour `schedule_time_local`, `schedule_weekday`, `schedule_day_of_month`, `schedule_timezone`; DST gap/overlap handling
- [x] Next slot anchored to `scheduled_for`, never `now`; no backlog replay
- [x] Property tests (`hypothesis`, `time-machine`) per design.md Testing Strategy

## 3. Crash safety and idempotency [#21]

- [x] Claim sets `claim_token`; all issue writes conditional on it; fenced-out worker logs and stops
- [x] Delivery `sending` committed before Resend call; recovery resends with same idempotency key
- [x] Startup assertion: `SCHEDULER_LOCK_TIMEOUT_MINUTES` > worst-case run duration
- [x] Integration tests: concurrent claim, stale takeover, fenced write is a no-op, crash after `sending` → one email
- [ ] Manual: `docker compose down` mid-run in staging → exactly one email — steps in `runbook.md`; **TODO: run in staging**

## 4. Email result and error classification [#22]

- [x] `EmailService.send` returns `SendResult(ok, message_id, error_kind, error)`; on-demand `routers/pdf.py` uses it
- [x] Classification: 429/5xx/timeout transient (honour `Retry-After`); other 4xx and missing config permanent
- [x] Escape all interpolated HTML; Resend `Idempotency-Key` header
- [x] Missing or unverified recipient is a permanent `config:` failure, not a success (missing/blank done; "unverified" waits for §7, which adds `target_email_verified_at`)
- [x] `respx` contract tests for every classification row; rendered-body snapshots
- [x] Add `openspec/specs/email-delivery/spec.md` on archive (delta in this change)

## 5. Retries, give-up, and owner notification [#23]

- [x] Backoff 1h/2h/4h/8h… cap 24h, max `SCHEDULER_MAX_ATTEMPTS` (5); abandon if next attempt ≥ next slot
- [x] Abandoned edition: issue advances to next slot, `last_run_error` set, owner give-up email sent once (`owner_notified_at`)
- [x] Frozen-clock tests: full retry ladder, daily period-boundary abandonment, notification idempotency
- [x] Verify the migration doesn't touch `auto_send=false` rows

## 6. Article selection

- [x] Window = `max(last sent articles_until, now - article_window_days)` → now; record `articles_from/until/count`
- [x] Zero articles → delivery `skipped`, no email, next slot
- [x] Tests: consecutive editions never overlap; first edition uses full window; manual send counts as last delivery

## 7. Recipient verification and unsubscribe

- [x] `POST /issues/{id}/target-email/verify` (owner, rate-limited), `GET /email/verify?token=` (confirming is a POST from a page; the emailed GET link only shows the page)
- [x] `PUT /issues/{id}`: 422 when enabling `auto_send` without verified recipient; validate schedule fields; fill weekday/day-of-month on enable
- [x] One-click unsubscribe endpoint + `List-Unsubscribe` / `List-Unsubscribe-Post` headers
- [x] API tests for token expiry, reuse, email changed since issuance, unsubscribe

## 8. Access control

- [x] `Depends(require_issue_owner)` verifying the Supabase JWT; apply to send-now, verify, deliveries (PR #50)
- [x] Next.js proxy routes forward `Authorization: Bearer <access_token>` (PR #50, plus the new verify / deliveries routes)
- [x] Remove `POST /pdf/trigger-scheduled/{id}`
- [x] Tests: 401 without token, 403 for non-owner (PR #50)

## 9. UI

- [x] Weekday / day-of-month / time pickers; timezone defaults to browser zone
- [x] Status panel from server `next_run_at` / `last_run_at` / `last_run_error`; remove `computeNextScheduled` (#23 added the retry/last-error/next-delivery lines via `ScheduleStatus`; the estimate remains as a fallback until the scheduler sets `next_run_at`)
- [x] Recipient verification state; auto-send toggle gated on verification
- [x] Send now button with 409/412 handling; delivery history list (`GET /issues/{id}/deliveries`) (409 and 429; verification is not required for Send now)
- [x] vitest coverage for the above

## 10. Ops and release

- [x] Remove `--reload` from production `docker-compose.yml`; scheduler shutdown waits for in-flight run
- [ ] Confirm SPF/DKIM/DMARC for the sending domain and Resend plan limits — checked 2026-10-20: DKIM and SPF verified, plan has 3000 emails/month and 100/day; **TODO: no DMARC record** (see `runbook.md`)
- [ ] Staging E2E with Resend test addresses — `newsletter2paper/tests/e2e/test_resend_staging.py` (opt-in); **TODO: run against staging**
- [x] Update `openspec/README.md` domain table (`scheduling`, `email-delivery`) and archive this change (table was already current; the change stays open until the items marked TODO below are done)

## Follow-ups (separate issues)

- [ ] Resend webhooks: pause auto_send on hard bounce/complaint
- [ ] Email table of contents; attach PDF when small
- [ ] Scheduler heartbeat in `/health` + alerting; PDF storage retention
- [ ] Separate worker container; revisit pgmq at higher volume
