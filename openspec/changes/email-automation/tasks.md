# Tasks: Email Automation

> **Status (2026-10-03):** Partially implemented. The remaining work is tracked in
> `openspec/changes/scheduled-delivery-hardening` (PR #5) and
> `openspec/changes/scheduled-delivery-production` (#17, #21–#23). The fine-grained schedule
> columns exist in the database, but the API, UI and scheduler do not use them yet, so those
> items are unchecked below.

## 1. Database

- [x] Add migration for scheduling columns and indexes on `issues`.
- [x] Apply migration to target environments.

## 2. Backend

- [x] Add scheduler service and lifecycle startup integration.
- [x] Implement due-issue claiming with lock-safe processing.
- [x] Add manual trigger endpoint `POST /pdf/trigger-scheduled/{issue_id}`.
- [x] Integrate email sending after successful PDF generation.
- [x] Persist `auto_send` through issue update/create paths.
- [ ] Persist fine-grained schedule fields through the API. The columns exist; `routers/issues.py` doesn't accept them. → scheduled-delivery-production §7
- [ ] Fine-grained next-run computation (weekday/day-of-month/time). Only the untracked `services/scheduling_utils.py` has it, and nothing imports it. → scheduled-delivery-production §2

## 3. Frontend

- [x] Persist `auto_send` from configuration UI (written directly to Supabase).
- [ ] UI controls for weekly weekday, monthly day-of-month, and send time. → scheduled-delivery-production §9

## 4. Verification

- [ ] Add/expand automated tests for scheduler state transitions. → PR #5, scheduled-delivery-production §3–§6
- [ ] ~~Add integration test for manual trigger endpoint.~~ Endpoint is being removed in favor of authenticated Send now. → scheduled-delivery-production §8
- [ ] Add end-to-end check for email send path in staging. → scheduled-delivery-production §10

## 5. Follow-up (separate change)

- [ ] Timezone selection beyond `UTC`. → scheduled-delivery-production §9 (browser default + picker)
