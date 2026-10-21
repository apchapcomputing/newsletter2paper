# Change Proposal: Email Automation

## Why
Users can manually generate PDFs, but they need automatic delivery by email on a recurring schedule.
This change standardizes scheduling fields and processing behavior so delivery is reliable and observable.

## What Changes

- Add issue-level automation fields used by the scheduler (`auto_send`, `next_run_at`, `last_run_at`, `schedule_status`, `article_window_days`, `last_run_error`, `locked_at`, `schedule_timezone`).
- Add fine-grained schedule controls for weekly/monthly delivery (`schedule_weekday`, `schedule_day_of_month`, `schedule_time_local`).
- Support automatic processing of due issues with safe row-level claiming.
- Add a manual trigger endpoint to run one scheduled issue on demand for testing.
- Send generated PDFs using Resend when automation is enabled.
- Persist `auto_send` changes from UI/API updates.

## Scope

- In scope: backend scheduling flow, DB state transitions, email delivery invocation, manual trigger endpoint, fine-grained weekday/day-of-month/time scheduling controls, and spec updates.

## Success Criteria

- Due issues with `auto_send=true` are processed once and rescheduled.
- Successful runs update `last_run_at`, clear errors, and set next run.
- Failed runs record `last_run_error` and set `schedule_status` appropriately.
- Manual trigger endpoint can process a single issue without waiting for scheduler cadence.
