# Issues Spec Delta — Email Automation

## MODIFIED Requirements

### Requirement: Issue Creation
The system SHALL allow creating an issue with title, format, frequency, and scheduling automation fields.

#### Scenario: Create issue with automation disabled by default

- GIVEN a valid `POST /issues/` request without automation fields
- WHEN the issue is created
- THEN `auto_send` is `false`
- AND `schedule_status` is `idle`

#### Scenario: Create issue with automation enabled

- GIVEN a valid `POST /issues/` request with `auto_send: true`
- WHEN the issue is created
- THEN scheduling fields are stored
- AND `next_run_at` is set according to frequency policy

---

### Requirement: Issue Update
The system SHALL allow partially updating scheduling automation fields.

#### Scenario: Enable automatic sending

- GIVEN an existing issue with `auto_send: false`
- WHEN the client sends `PUT /issues/{id}` with `auto_send: true`
- THEN the issue persists `auto_send=true`
- AND `next_run_at` is set or retained per scheduling policy

#### Scenario: Disable automatic sending

- GIVEN an existing issue with `auto_send: true`
- WHEN the client sends `PUT /issues/{id}` with `auto_send: false`
- THEN future scheduler processing for that issue is skipped

---

## ADDED Requirements

### Requirement: Fine-Grained Schedule Fields
The system SHALL support additional schedule fields for automatic delivery behavior.

#### Scenario: Weekly schedule stores weekday and send time

- GIVEN `auto_send=true`, `frequency=weekly`, `schedule_weekday=4`, and `schedule_time_local=09:00`
- WHEN the issue is created or updated
- THEN `schedule_weekday` and `schedule_time_local` are persisted
- AND `next_run_at` is computed using those values

#### Scenario: Monthly schedule stores day-of-month and send time

- GIVEN `auto_send=true`, `frequency=monthly`, `schedule_day_of_month=1`, and `schedule_time_local=09:00`
- WHEN the issue is created or updated
- THEN `schedule_day_of_month` and `schedule_time_local` are persisted
- AND `next_run_at` is computed using those values

#### Scenario: Invalid schedule values rejected

- GIVEN `schedule_weekday` outside `0..6` or `schedule_day_of_month` outside `1..31`
- WHEN the client sends `POST /issues/` or `PUT /issues/{id}`
- THEN a 422 validation error is returned

### Requirement: Scheduling State Persistence
The system SHALL persist scheduler execution state on each issue.

#### Scenario: Successful scheduled run updates state

- GIVEN a due issue is processed successfully
- WHEN the run completes
- THEN `last_run_at` is updated
- AND `schedule_status` becomes `idle`
- AND `last_run_error` is cleared
- AND `next_run_at` is advanced

#### Scenario: Failed scheduled run records error

- GIVEN a due issue run fails
- WHEN the run completes with failure
- THEN `schedule_status` becomes `failed` or equivalent retry state
- AND `last_run_error` stores an error message

---

### Requirement: Scheduler Concurrency Safety
The system SHALL prevent duplicate processing of the same issue across workers.

#### Scenario: Multiple workers polling due issues

- GIVEN two scheduler workers poll at the same time
- WHEN they claim due rows
- THEN each issue is claimed by at most one worker via row locking semantics
