# Implementation plan: scheduler hardening (P0, M1)

Scope: the five P0 scheduler bugs in GitHub Project #6, all in `newsletter2paper/services/scheduler.py`.
Decisions (confirmed): enabling auto_send waits for the first cadence and a "Send now" button/endpoint sends immediately; if email fails after the PDF was generated, retry the email only.
Status: implemented; see tasks.md. This file is the original plan and is kept for reference.

## 0. Test harness (prerequisite)
- Add `tests/unit/test_scheduler.py`. Refactor `SchedulerService` minimally so it is testable without Postgres/Docker:
  - split pure logic out: `compute_next_run(freq, now, tz) -> datetime | None` (no DB write; currently `_compute_next_run` disables `auto_send` as a side effect).
  - inject `engine`, `pdf_service`, `email_service` via constructor args (default to current behavior).
- Use SQLite-free fakes: mock engine/connection; test SQL-issuing methods by asserting on statements + params.

## 1. Stale `processing` lock reclaim
- Poll query: also select `schedule_status='processing' AND locked_at < now() - interval '15 minutes'`.
- Reset `locked_at` on claim. Threshold from env `SCHEDULER_LOCK_TIMEOUT_MINUTES` (default 15, > 120s PDF timeout).

## 2. Retry failed runs with backoff
- Poll selects `schedule_status IN ('idle','failed')` with `next_run_at <= now()`.
- Add `run_attempts int default 0` (migration `data/migrations/2026_10_04_scheduler_hardening.sql`); failure: `next_run_at = now() + interval '1 hour' * 2^attempts` (cap 24h); after 5 attempts leave `failed`, stop auto-retry, keep `last_run_error`.
- Reset `run_attempts=0` on success.

## 3. Email failures are recorded, not swallowed
- `_process_issue`: check `send_pdf` return + catch exceptions; set `last_run_error='email: ...'`.
- Decision (recommend): PDF was generated so do NOT resend the PDF pipeline; retry email only (next attempt reuses stored `pdf_url`). Keep it simple first: mark run `failed` with attempts logic from step 2.
- Align with on-demand path in `routers/pdf.py` (`email_sent` / `email_error`).

## 4. Per-period idempotency
- Add `last_sent_period text` (e.g. `2026-W40`, `2026-10-01`, `2026-10`) computed from frequency + tz; skip send if equal to current period key; set only after successful email.
- Migration in same file as step 2.

## 5. Real cadence + timezone
- `compute_next_run` uses `zoneinfo.ZoneInfo(issue['schedule_timezone'] or 'UTC')`, `dateutil.relativedelta(months=1)` for monthly (clamp to month end), preserve local wall-clock time across DST.
- Move `auto_send=false` for once/custom into caller.

## 6. First-run timing on enable
- Decision needed from owner: first send immediately vs. at the first cadence boundary. Recommend: when `auto_send` flips true (in `routers/issues.py` create/update), set `next_run_at = now()` only if user asks "send now"; otherwise next boundary. Poll no longer treats NULL as due (`next_run_at <= now()` only); migration backfills NULL for existing `auto_send` rows.

## 7. Specs/docs
- Update `openspec/specs/scheduling` and `email-delivery`; tick `tasks.md`; remove "Known gaps" line from CLAUDE.md.

## Verification
- `pytest tests/unit/test_scheduler.py`; manual: `POST /pdf/trigger-scheduled/{issue_id}` against a dev Supabase with a forced failure (bad email key) and a killed container mid-run.
- Migration applied manually to Supabase before deploying (no runner) — call out in PR.

## Open questions
1. First-run behavior (step 6).
2. Email-failure: retry whole run vs. email only (step 3).
