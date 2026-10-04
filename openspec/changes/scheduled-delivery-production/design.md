# Design: Production-Ready Scheduled Delivery

## Overview

The scheduler keeps polling `issues` with `FOR UPDATE SKIP LOCKED`. That already works as a queue at this volume, so pgmq is deferred. What changes is where per-edition state lives. The `issues` row holds the **schedule** (what to send and when). A new `issue_deliveries` row holds each **edition** (what happened). Idempotency, retries, crash recovery, article selection and the history UI all read from delivery rows.

```
issues (schedule)                         issue_deliveries (one row per edition)
  auto_send, frequency, schedule_*  ──┐     period_key, scheduled_for, trigger
  next_run_at   (next slot or retry)  │     status, attempts, next_attempt_at
  schedule_status, locked_at,         └──►  pdf_url, articles_from/until, articles_count
  claim_token, last_run_at,                 recipient, resend_message_id
  last_run_error (denormalised for UI)      error_kind, error, owner_notified_at
```

## Data Model

### New table `public.issue_deliveries`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Also used to derive the Resend idempotency key |
| `issue_id` | uuid FK → `issues(id)` ON DELETE CASCADE | |
| `trigger` | text CHECK IN (`scheduled`, `manual`) | |
| `period_key` | text NULL | Required for `scheduled`, NULL for `manual` |
| `scheduled_for` | timestamptz NOT NULL | The slot being served (`now()` for manual) |
| `status` | text CHECK IN (`pending`, `sending`, `sent`, `skipped`, `failed`, `abandoned`) | |
| `attempts` | int NOT NULL DEFAULT 0 | |
| `next_attempt_at` | timestamptz NULL | Set while `failed` |
| `articles_from` / `articles_until` | timestamptz | Window actually used; `articles_until` drives the next edition |
| `articles_count` | int | |
| `pdf_url` | text | Reused by email-only retries |
| `recipient` | text | Address used for this send |
| `resend_message_id` | text | For bounce correlation (webhook follow-up) |
| `error_kind` | text CHECK IN (`transient`, `permanent`) NULL | |
| `error` | text NULL | User-readable, prefixed `pdf:` / `email:` / `config:` |
| `owner_notified_at` | timestamptz NULL | The give-up email is sent at most once |
| `created_at`, `updated_at`, `sent_at` | timestamptz | |

Indexes and constraints:

- `UNIQUE (issue_id, period_key) WHERE trigger = 'scheduled'`: idempotency enforced by the database.
- `(issue_id, sent_at DESC) WHERE status = 'sent'`: previous-edition lookup and history.

RLS: owners can `SELECT` their own issues' deliveries (same ownership check as `issues`). There are no client write policies; only the scheduler (direct Postgres connection) writes.

### `issues` changes

- **Add:** `claim_token uuid`, `target_email_verified_at timestamptz`, `unsubscribe_token uuid DEFAULT gen_random_uuid()`.
- **Do not add** PR #5's `run_attempts`, `last_sent_period`, `pending_pdf_url`, `pending_period`. Remove them from PR #5's migration before it ships.
- **Column privileges:** `REVOKE UPDATE` from `anon` and `authenticated` on `next_run_at`, `schedule_status`, `locked_at`, `claim_token`, `last_run_at`, `last_run_error`, `target_email_verified_at`, `unsubscribe_token`. Writes go through the API (service role) or triggers.
- **Trigger** `reset_schedule_on_cadence_change` (replaces PR #5's auto_send-only trigger):
  - fires `BEFORE UPDATE OF auto_send, frequency, schedule_timezone, schedule_time_local, schedule_weekday, schedule_day_of_month`;
  - sets `next_run_at = NULL` so the scheduler recomputes from the new settings;
  - marks any open (`pending` / `failed`) scheduled delivery `abandoned` with error `config: schedule changed`, without notifying the owner.
- **Trigger** `reset_verification_on_email_change`: `BEFORE UPDATE OF target_email` clears `target_email_verified_at`, unless the new address equals the owner's confirmed `auth.users.email`, in which case it sets it to `now()`.

### New table `public.email_verifications`

Columns: `id`, `issue_id`, `email`, `token_hash` (sha256), `expires_at` (24h), `consumed_at`, `created_at`. No client access.

## Scheduling Math

Lives in `services/scheduling.py` as pure functions with no I/O, merged from the untracked `scheduling_utils.py` and PR #5's `period_key`.

- `slot_after(issue, t) -> datetime | None`: the first slot strictly after `t` in `schedule_timezone`, at `schedule_time_local` (default `09:00`):
  - daily: every day;
  - weekly: on `schedule_weekday` (0 = Monday);
  - monthly: on `schedule_day_of_month`, clamped to the month's last day;
  - `once` / `custom`: None.
  - Built from local wall-clock values and then localised, so DST does not shift the time. A slot that doesn't exist on spring-forward day moves forward to the first valid minute. On fall-back day the first occurrence of an ambiguous time is used (`fold=0`).
- `period_key(issue, scheduled_for)`: computed from the **slot**, never from processing time. Daily `YYYY-MM-DD`, weekly ISO `YYYY-Www`, monthly `YYYY-MM`, all in `schedule_timezone`.
- Next slot after a delivery finishes, whatever the outcome: `slot_after(issue, max(scheduled_for, now - 1 period))`, then advanced until it is in the future. Missed slots are never replayed, so after downtime at most one catch-up edition is sent.
- Enabling, or any cadence change: `next_run_at = slot_after(issue, now)`. Nothing is sent immediately; Send now covers that.
- When `auto_send` is enabled with `schedule_weekday` / `schedule_day_of_month` NULL, the API fills them from the current local date and saves them, so the slot stays fixed.

## Run Lifecycle

```
poll ─► claim issue (SKIP LOCKED; idle, failed-and-due, or processing with locked_at > LOCK_TIMEOUT)
         set schedule_status='processing', locked_at=now(), claim_token=gen_random_uuid()
      ─► open delivery = scheduled delivery in (pending, failed, sending), else
         INSERT (period_key from next_run_at) ON CONFLICT DO NOTHING
           conflict with status 'sent' → advance next_run_at, release, stop
      ─► recipient checks: no target_email or not verified → permanent 'config:' failure
      ─► pdf_url present? reuse (email-only retry) : fetch articles + render
           0 articles → status 'skipped', advance, release (no email)
           render error → transient failure
      ─► UPDATE delivery SET status='sending', recipient, pdf_url, articles_* (committed)
      ─► Resend send with Idempotency-Key = "delivery-{id}-{attempts}"
      ─► success   → delivery 'sent'; issue next_run_at = next slot, last_run_at, error cleared
         transient → attempts++, next_attempt_at = now + backoff; if that is >= the next slot
                     or attempts == MAX → abandoned
         permanent → abandoned
         abandoned → issue next_run_at = next slot; send the give-up email once
      ─► every issue write: ... WHERE id = :id AND claim_token = :token
```

- **Fencing (#21):** a worker whose claim was taken over after `LOCK_TIMEOUT` finds that its token no longer matches. Its writes update 0 rows; it logs this and stops. `LOCK_TIMEOUT` (default 15 min) must exceed the worst-case run (RSS fetch + 120s render + email); a startup check asserts it.
- **Crash between Resend accepting and the row update:** the recovered run finds the delivery `sending` and resends with the **same** idempotency key (attempt number unchanged). Resend deduplicates within 24h, which is well inside `LOCK_TIMEOUT` + recovery.
- **Retry poll:** a `failed` delivery puts its `next_attempt_at` on `issues.next_run_at` and sets `schedule_status = 'failed'`, so the existing poll picks it up.

## Email Delivery

`EmailService.send(...)` returns `SendResult(ok, message_id, error_kind, error)` instead of a bool:

- `permanent`: Resend 4xx except 429 (invalid address, unverified domain), missing `RESEND_API_KEY` / `EMAIL_FROM`.
- `transient`: 429 (respecting `Retry-After` as a minimum backoff), 5xx, network errors and timeouts.
- `routers/pdf.py` (on-demand) maps `SendResult` to `email_sent` / `email_error` as it does today.

Every delivery email:

- escapes all interpolated values;
- carries the idempotency key, plus `List-Unsubscribe: <https://…/unsubscribe?t={unsubscribe_token}>, <mailto:…>` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`.

Unsubscribing sets `auto_send = false` (via the API, service role) and shows a confirmation page with a re-enable link. Owner notifications (give-up, verification) are transactional: they are sent to the owner's account email and are not tied to an issue's `auto_send`.

## Article Selection

- `articles_until` = render time.
- `articles_from` = `max(last sent delivery's articles_until, articles_until - article_window_days)`, or the full window when nothing has been sent.
- "Last sent delivery" includes manual sends, so Send now followed by a scheduled edition does not repeat articles (see open question 1).
- Uses the existing `start_date` / `end_date` parameters of `RSSService.fetch_recent_articles_for_issue`.

## API

- `POST /issues/{id}/send-now`:
  - requires a Supabase JWT whose user owns the issue;
  - 404 if the issue doesn't exist, 400 if there is no recipient, 409 if a run is already in progress, 412 if the recipient is unverified;
  - creates a `manual` delivery and does not touch `next_run_at`;
  - uses `request.app.state.scheduler`, not a new `SchedulerService()`.
- `POST /issues/{id}/target-email/verify`: owner only. Sends a confirmation link; rate limited to 3 per hour per issue.
- `GET /email/verify?token=…`: sets `target_email_verified_at` when the token matches, hasn't expired, and the issue's email hasn't changed since.
- `POST /email/unsubscribe?t=…`: one-click; `GET` renders a confirmation page.
- `GET /issues/{id}/deliveries?limit=20`: owner only. Feeds the history UI.
- `PUT /issues/{id}` accepts and validates `schedule_timezone` (IANA), `schedule_time_local` (`HH:MM`), `schedule_weekday` (0–6) and `schedule_day_of_month` (1–31). Setting `auto_send = true` without a verified recipient returns 422.
- Removed: `POST /pdf/trigger-scheduled/{id}` (Send now replaces it).

The Next.js proxy routes forward the user's `Authorization: Bearer <access_token>`. The backend verifies it with Supabase. This is the first authenticated backend endpoint; the guard is a reusable `Depends(require_issue_owner)`.

## UI (`ConfigureNewspaper.js`)

- **Schedule controls:**
  - weekday picker (weekly), day-of-month picker (monthly, with "29–31 move to the month's last day" help text), time picker;
  - timezone defaults to `Intl.DateTimeFormat().resolvedOptions().timeZone` and can be changed.
- **Status panel from server fields only** (removes the client-side `computeNextScheduled`):
  - next delivery, last delivery, and the current error with a plain-language message;
  - "Retrying at …" while `failed`.
- **Recipient:** prefilled with the account email (verified). Changing it shows "Unverified – send confirmation". The auto-send toggle stays disabled until the recipient is verified.
- **Actions:** Send now; delivery history list (last 10: date, status, articles count, PDF link while the signed URL is valid).

## Testing Strategy

| Layer | Tooling | Covers |
| --- | --- | --- |
| Scheduling math | pytest + `hypothesis` + `time-machine` | Slot is always in the future and on the configured weekday / day / local time; idempotent; DST gaps and overlaps (America/New_York, Europe/London, Australia/Lord_Howe 30-minute shift); Feb 28/29, 30/31-day months; year rollover; invalid timezone → UTC; period key computed from the slot |
| State machine | pytest + fakes (extends PR #5 `test_scheduler.py`) | Every transition in the run lifecycle, fencing no-op, retry deadline at the period boundary, give-up notification sent once, email-only retry reuses PDF and idempotency key |
| Database | local Supabase in CI (`test-db-migrations.yml`) + pytest-postgres fixtures + pgTAP | Two connections claiming at once with `SKIP LOCKED`; stale-lock takeover; unique period index; cadence and email triggers; column `REVOKE`s for `anon` / `authenticated`; delivery RLS |
| Email | pytest + `respx` against the Resend HTTP API | Error classification table (200 / 422 / 429 / 500 / timeout / missing key); headers (idempotency, List-Unsubscribe); HTML escaping; snapshot of rendered bodies |
| API | FastAPI TestClient | Ownership guard (401 / 403), send-now status codes, verify / unsubscribe token flows, 422 on enabling without a verified recipient |
| UI | vitest + Testing Library | Schedule controls round-trip, timezone default, status panel renders server state, verification gating, Send now states |
| Staging E2E | Resend test inboxes (`delivered@`, `bounced@`, `complained@resend.dev`) | Real send, permanent failure path, `docker compose down` mid-run → exactly one email |

## Rollout

1. Rebase PR #5 onto `main`. Move its migration into `newsletter2paper/supabase/migrations/` and remove the columns this design replaces. Merge.
2. Ship this change's migration (it is additive). Backfill:
   - `target_email_verified_at = now()` where `target_email` matches the owner's confirmed account email;
   - other `auto_send` issues are verified on the owner's next visit; until then their sends fail with a permanent `config:` error that tells the owner what to do.
3. Deploy the backend, then the UI.
4. Staging E2E, then watch the first production week of the owner's "Economics for Everyone" issue.

## Open Questions

1. Should manual Send now count as "last delivery" for article selection? Default: yes, so no repeats.
2. Owner email for notifications: read `auth.users.email` through the direct Postgres connection (service role). Confirm this is acceptable versus storing `owner_email` on `issues`.
