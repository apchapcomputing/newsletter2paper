# Plan: Issue #23 - Failed scheduled issues are retried, never cross periods, and never fail silently

Branch: `feature/retry-within-period-and-giveup` (from `main`). Spec: this change's `specs/scheduling/spec.md`
(*Retry Policy*, *Owner Failure Notification*, *Next Run Computation*), `tasks.md` §2 (the parts it needs) and §5.

## Where main is today

PR #5 and the claim/delivery work (#21) are merged, so the retry ladder, `issue_deliveries`, `claim_token`
fencing and `owner_notified_at` (column only) exist. What is still wrong, in `services/scheduler.py`:

| Issue item | Today | Consequence |
| --- | --- | --- |
| 1. Stay in period | `_fail` sets `retry_at = now + retry_delay(n)` with no look at the next slot | A late retry can land after the next slot; the next edition then finds an open `failed` delivery and is served by it (or skipped) |
| 2. Keep the slot | `_next_slot` -> `compute_next_run(frequency, now, tz)` adds 1 day / 7 days / 1 month to *now*; `schedule_time_local`, `schedule_weekday`, `schedule_day_of_month` are ignored | A success 6h late moves every later delivery 6h later, permanently. Same in `_initialize_unscheduled` |
| 3. Give-up | `_fail` at `MAX_RUN_ATTEMPTS` sets `last_run_error` and advances. No owner email; `owner_notified_at` never written | Owner is never told |
| 4. UI | `ConfigureNewspaper` shows a client-side guess (`computeNextScheduled`); nothing shows `schedule_status` / `last_run_error` | "Silently stops" is invisible |

Also noticed: `release_after_error` (error before a delivery exists) sets `next_run_at = now + 1h` and `failed`; the retry
then derives `scheduled_for` from that shifted `next_run_at`, so the edition's slot and period are wrong. Fixed in step 2.

## Steps (one commit each, tests first)

### 1. `services/scheduling.py` (pure, no I/O) - the slice of tasks §2 this issue needs
- `slot_after(issue, t) -> datetime | None`: first slot strictly after `t` in `schedule_timezone` at `schedule_time_local`
  (default 09:00). daily = every day; weekly = `schedule_weekday`; monthly = `schedule_day_of_month` clamped to month end;
  `once`/`custom` = None. Built from local wall-clock values then localised (DST gap moves forward, overlap uses `fold=0`).
- When `schedule_weekday` / `schedule_day_of_month` is NULL, fall back to the **anchor's** weekday / day-of-month. This keeps
  the slot stable without needing the API change from tasks §7.
- `next_slot_after_delivery(issue, scheduled_for, now)`: `slot_after(issue, max(scheduled_for, now - 1 period))`, advanced
  until in the future. Missed slots are not replayed.
- `retry_deadline(issue, scheduled_for)`: the next slot after `scheduled_for` (None for one-shot).
- Move `period_key`, `retry_delay` here from `scheduler.py` (re-export for now). Delete `compute_next_run` / `_add_months`
  once nothing uses them (port their tests).

### 2. Anchor the schedule to the slot (issue item 2)
- `_next_slot(issue, now)` -> `_next_slot(issue, scheduled_for, now)` using `next_slot_after_delivery`; `_succeed`, `_skip`,
  `_advance` pass `delivery['scheduled_for']`. `_initialize_unscheduled` uses `slot_after(issue, now)`.
- `release_after_error` (no delivery yet): keep `next_run_at` unchanged instead of shifting it, so the slot survives.
- No migration needed for this step.

### 3. Retry deadline (issue item 1)
- In `_fail`, after computing `retry_at = now + retry_delay(attempts)`: if `retry_deadline` exists and `retry_at >= deadline`,
  treat as give-up with reason `retry window closed` (distinct message from "gave up after N attempts").
- Period key is always taken from the open delivery (already true) or `scheduled_for`; add an assertion/log if an open
  delivery's period differs from `period_key(delivery.scheduled_for)`.

### 4. Give-up handling + one-time owner notice (issue item 3)
- Single `_abandon(...)` used by: attempts exhausted, retry window closed, and (after #22) permanent errors. Keeps
  `auto_send` on, advances to next slot, sets `last_run_error`, marks the delivery `abandoned`.
- `DeliveryStore.claim_owner_notice(delivery_id)`: `UPDATE ... SET owner_notified_at = now() WHERE id = :id AND owner_notified_at IS NULL RETURNING ...`
  (returns issue title, period, error, owner id). Whoever gets the row sends; everyone else does nothing.
- Send with Resend `Idempotency-Key: owner-notice-{delivery_id}`. If the send raises/fails, reset `owner_notified_at = NULL` so the
  next poll retries; the idempotency key makes a duplicate harmless inside Resend's 24h window.
- Crash recovery: each poll also sweeps `abandoned` deliveries with `owner_notified_at IS NULL` (bounded, e.g. last 7 days), so a
  crash between "abandoned" and "email" still ends in exactly one notice.
- Owner address: `auth.users.email` via the existing direct Postgres connection, joined through `user_issues` (production has no
  `public.users`). This resolves design open question 2; it needs your OK (see Questions).
- `EmailService.send_owner_notice(to, issue_title, period, reason, idempotency_key)`: small, escaped template. #22 will fold this into
  `SendResult`; until then it returns bool/raises like `send_pdf_message`.
- Migration `20261006000000_owner_notice_schedule_change.sql`: replace `reset_schedule_on_cadence_change` so the edition it abandons with
  `config: schedule changed` also gets `owner_notified_at = now()` (never notified). Idempotent `CREATE OR REPLACE`.
- Errors `config: schedule changed` are also excluded in the sweep as belt and braces.

### 5. Show it to the user (issue item 4)
- Read-only status from server fields: `schedule_status`, `next_run_at`, `last_run_error` for `currentIssueId`
  (owner can already `SELECT` their issue under RLS; no new endpoint).
- `ConfigureNewspaper`: "Retrying at <local time>" when `schedule_status = 'failed'`; last error after give-up (kept until the next success);
  replaces the client-side `computeNextScheduled` text with `next_run_at` when present. Plain-language mapping of the `pdf:` / `email:` / `config:` prefixes.
- Scoped to this status line; the full status panel / history stays in tasks §9.

## Tests (per the issue)
- `tests/unit/test_scheduling.py` (new): `time-machine` frozen clock. Slot is future and on configured weekday/day/time; monthly clamp (31 -> Feb);
  DST gap and overlap (America/New_York, Europe/London); NULL weekday falls back to anchor; no backlog replay after downtime; period key from slot.
  Add `hypothesis` for "slot_after is strictly after t, idempotent, right local time" (new dev deps: `time-machine`, `hypothesis`).
- `tests/unit/test_scheduler.py` extended with fake store:
  - full ladder 1h/2h/4h/8h then give-up, asserting `next_run_at`, delivery status, `last_run_error`, `auto_send` still true;
  - daily 09:00 issue whose retry would pass the next 09:00 is abandoned and `next_run_at` is the next day's slot;
  - **success on attempt 3 keeps next week's slot** (weekly Friday 09:00 NY, succeeds 16:00 -> next Friday 09:00 NY);
  - give-up notice sent exactly once: twice-processed abandoned delivery, crash after `abandoned`/before email (sweep resends with the same key),
    send failure resets the flag, schedule-change abandonment never notifies.
- `tests/integration/test_delivery_store_pg.py` (existing PG harness): `claim_owner_notice` is atomic under two connections;
  the `20261001` stuck-`failed` fix and the new trigger migration leave `auto_send = false` rows untouched.
- `ui/tests`: status line renders "Retrying at ..." for `failed`, the last error after give-up, and nothing for a healthy issue.
- Manual (staging): force Resend 503 on a daily issue -> observe 1h/2h/4h/8h and a clean give-up email; `docker compose down` mid-notice -> one email.

## Out of scope (other issues)
Error classification / `SendResult` (#22 - this plan calls `_abandon` for permanent errors once #22 lands), recipient verification, API
ownership checks (#25), delivery history UI, article-window selection (tasks §6).

## Order and risk
Steps 1-3 are pure logic plus scheduler edits and can ship alone (fixes items 1-2, no migration). Step 4 adds the only migration and the only new
outbound email. Step 5 is UI only. Risk: changing `_next_slot` shifts existing issues from "now + interval" to the configured slot; for rows with
NULL weekday the anchor fallback makes the first computed slot equal to today's behaviour, so nothing jumps on deploy.

## Questions for you
1. OK to read the owner address from `auth.users.email` via the service connection (design open question 2), rather than storing `owner_email` on `issues`?
2. Should a give-up on a **one-shot** (`once`/`custom`) issue notify and then turn `auto_send` off, or keep retrying daily as `_fail` does now? Plan: notify, then leave as today (retry tomorrow) - say if you'd rather stop.
3. Do #23 before #22 (plan assumes yes: `_abandon` takes a `kind`, #22 only supplies `permanent`)?
