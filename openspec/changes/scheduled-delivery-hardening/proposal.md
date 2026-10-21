# Scheduled delivery hardening

## Why

GitHub project item "Email service: daily / weekly / monthly delivery schedule" is marked In progress, but a
first version already ships: per-issue `auto_send` + `frequency` driving `services/scheduler.py`, and Resend
delivery. What remains is correctness and durability.

## What

- **Idempotency:** guard against a second email for the same period (today only `SKIP LOCKED` prevents concurrent runs; a retry after a failed email or a stuck `processing` row can resend or never recover).
- **Stale locks:** reclaim rows stuck in `processing` (`locked_at` older than a threshold).
- **Email failure handling:** the scheduled path swallows email errors and still marks the run successful; record them in `last_run_error`.
- **Real cadence:** `monthly` is currently +30 days; use calendar months and honour `schedule_timezone`.
- **Failed-run retry:** failed issues (`schedule_status='failed'`) are never re-polled.
- **First run:** `next_run_at IS NULL` counts as due, so enabling `auto_send` triggers an immediate send; nothing sets `next_run_at` on enable.
- **Durable jobs (later):** move PDF generation and email to pgmq queues (project item "Introduce pgmq").

## Specs affected

`scheduling`, `email-delivery`.
