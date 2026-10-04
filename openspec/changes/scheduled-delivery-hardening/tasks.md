# Tasks

- [x] Per-period idempotency key so an issue is emailed at most once per period
- [x] Reclaim `processing` rows with stale `locked_at`
- [x] Record scheduled email failures in `last_run_error`; retry email only (reuse `pending_pdf_url`)
- [x] Calendar-month and timezone-aware next-run computation
- [x] Retry `failed` issues with exponential backoff (max 5 attempts, then wait for next period)
- [x] First run waits for the first cadence; `POST /issues/{id}/send-now` + UI "Send now" button
- [x] Scheduler unit tests (`tests/unit/test_scheduler.py`)
- [ ] Apply `data/migrations/2026_10_01_scheduler_hardening.sql` to Supabase before deploying
- [ ] Manual verification against a dev Supabase (forced email failure, killed container mid-run)
- [ ] pgmq queues for pdf_generation / email_delivery (follow-up)
