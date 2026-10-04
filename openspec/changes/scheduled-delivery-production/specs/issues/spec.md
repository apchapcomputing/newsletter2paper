# Issues Spec Delta: Production-Ready Scheduled Delivery

## ADDED Requirements

### Requirement: Automatic Delivery Settings

The system SHALL accept and validate the schedule fields on `POST /issues/` and `PUT /issues/{id}`:

- `schedule_timezone`: a valid IANA name;
- `schedule_time_local`: `HH:MM`, 00:00–23:59;
- `schedule_weekday`: 0–6;
- `schedule_day_of_month`: 1–31.

The UI SHALL write these fields only through the API.

#### Scenario: Invalid schedule values rejected

- GIVEN `schedule_timezone="Mars/Olympus"`, `schedule_time_local="25:00"`, `schedule_weekday=7` or `schedule_day_of_month=0`
- WHEN the client sends `POST /issues/` or `PUT /issues/{id}`
- THEN a 422 validation error is returned

#### Scenario: Enabling fills a missing slot day

- GIVEN a weekly or monthly issue with `schedule_weekday` or `schedule_day_of_month` NULL
- WHEN `auto_send` is set to true
- THEN the missing field is set from the current date in `schedule_timezone` and stored

#### Scenario: Enabling requires a verified recipient

- GIVEN an issue whose `target_email` is missing or unverified
- WHEN the client sends `PUT /issues/{id}` with `auto_send: true`
- THEN a 422 error explains that the recipient must be verified, and `auto_send` stays false

---

### Requirement: Delivery Status Exposure

The system SHALL return `next_run_at`, `last_run_at`, `schedule_status`, `last_run_error` and `target_email_verified_at` with issue reads, so the UI can show delivery status from server state only.

#### Scenario: UI shows the server's next delivery

- GIVEN an issue with `next_run_at` set by the scheduler
- WHEN the owner opens the configuration page
- THEN the displayed next delivery time is `next_run_at` in the owner's timezone, not a value computed on the client
