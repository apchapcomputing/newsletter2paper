# Design: Email Automation

## Overview
A background scheduler scans for due issues and claims work using database locking semantics to avoid duplicate processing across multiple instances. Each claimed issue runs the existing PDF generation pipeline and then sends an email when configured.

## Components

- Scheduler service:
  - Periodically queries due issues (`next_run_at <= now`) with `auto_send=true`.
  - Claims rows with `FOR UPDATE SKIP LOCKED` behavior.
  - Marks an issue `running`, executes processing, then marks `idle` or `failed`.
- PDF pipeline:
  - Reuses existing generation flow and storage upload.
- Email service:
  - Uses Resend API with `RESEND_API_KEY` and `EMAIL_FROM`.
  - Sends PDF URL/content after successful generation.

## Data Model
Uses scheduling columns on `issues`:

- `auto_send` boolean
- `article_window_days` integer
- `next_run_at` timestamptz
- `last_run_at` timestamptz
- `locked_at` timestamptz
- `schedule_status` text
- `last_run_error` text
- `schedule_timezone` text
- `schedule_time_local` text (`HH:MM`)
- `schedule_weekday` int (`0=Monday..6=Sunday`, weekly only)
- `schedule_day_of_month` int (`1..31`, monthly only)

## State Transitions

- `idle` -> `running` when claimed
- `running` -> `idle` on success
- `running` -> `failed` on unrecoverable error

On success:

- update `last_run_at`
- compute and set `next_run_at` from frequency + fine-grained fields (`schedule_time_local`, `schedule_weekday`, `schedule_day_of_month`, `schedule_timezone`)
- clear `last_run_error`

On failure:

- set `last_run_error`
- keep/update `next_run_at` according to retry policy (implementation-defined)

## API Surface

- Existing issue create/update/read APIs persist and expose automation fields.
- Manual test endpoint:
  - `POST /pdf/trigger-scheduled/{issue_id}`
  - Executes one issue through scheduler processing path.

## Operational Notes

- Requires direct Postgres connection string for lock-based claiming.
- Scheduler dependencies must exist in runtime image.
- Multiple app replicas are supported through `SKIP LOCKED` semantics.
