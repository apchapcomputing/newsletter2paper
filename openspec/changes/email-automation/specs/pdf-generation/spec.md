# PDF Generation Spec Delta — Email Automation

## ADDED Requirements

### Requirement: Scheduled PDF Processing
The system SHALL support processing scheduled issues without direct user initiation.

#### Scenario: Due issue triggers generation

- GIVEN an issue with `auto_send=true` and `next_run_at <= now`
- WHEN the scheduler executes
- THEN the issue is processed through the standard PDF generation pipeline

#### Scenario: Weekly schedule executes on configured weekday/time

- GIVEN an issue configured with `frequency=weekly`, `schedule_weekday=4`, and `schedule_time_local=09:00`
- WHEN a run completes successfully
- THEN the next `next_run_at` is set to the next matching weekday/time window

#### Scenario: Monthly schedule executes on configured day/time

- GIVEN an issue configured with `frequency=monthly`, `schedule_day_of_month=1`, and `schedule_time_local=09:00`
- WHEN a run completes successfully
- THEN the next `next_run_at` is set to the next matching day-of-month/time window

---

### Requirement: Email Delivery After Generation
The system SHALL send email delivery for successful scheduled runs.

#### Scenario: Scheduled run sends email

- GIVEN a scheduled issue run generates a PDF successfully
- WHEN processing completes
- THEN the system sends an email using configured provider credentials
- AND includes the generated PDF (attachment or accessible URL per implementation)

#### Scenario: Email provider not configured

- GIVEN scheduler processing succeeds but email provider credentials are missing
- WHEN email send is attempted
- THEN the run records an error state and message for operator visibility

---

### Requirement: Manual Scheduled Trigger
The system SHALL provide a manual endpoint to trigger scheduled processing for one issue.

#### Scenario: Manual trigger executes scheduler path

- GIVEN an existing issue id
- WHEN the client sends `POST /pdf/trigger-scheduled/{issue_id}`
- THEN the system runs that issue via scheduler processing logic
- AND returns success/failure details
