# Email Delivery Specification

## Purpose

Sending newspaper PDF links through Resend (`services/email_service.py`), for scheduled and manual
deliveries and for on-demand generation. Recipient verification and unsubscribe are still proposed
in `openspec/changes/scheduled-delivery-production` (tasks §7).

---

## Requirements

### Requirement: Structured Send Result

The system SHALL return a `SendResult` for every send attempt with `ok`, `message_id`, `error_kind`
(`transient` | `permanent`), a user-readable `error` and, when Resend sent one, `retry_after` in seconds.
`error` is prefixed `email:` when the provider refused or failed and `config:` when our setup is wrong.
Sending SHALL NOT raise or report failure as a bare boolean.

#### Scenario: Scheduled send fails

- GIVEN Resend rejects a scheduled delivery email
- WHEN the scheduler records the result
- THEN the delivery's `error` and `error_kind` and `issues.last_run_error` contain the cause, for example `email: Resend rejected the message (422: Invalid `to` field.)`

#### Scenario: On-demand generation reports email outcome

- GIVEN a user generates a PDF on demand (`POST /pdf/generate/{issue_id}`) for an issue with a `target_email`
- WHEN the email send fails
- THEN the response still succeeds with the PDF, and includes `email_sent: false`, `email_error` (the cause) and `email_error_kind`

---

### Requirement: Error Classification

The system SHALL classify send failures as follows:

- `transient`: HTTP 429, HTTP 5xx, network errors and timeouts (`RESEND_TIMEOUT_SECONDS`, 30), and 409 `concurrent_idempotent_requests`.
- `permanent`: any other HTTP 4xx (for example an invalid address, an unverified sending domain, or an idempotency key reused with a different payload), an API key Resend rejects (401, or 403 `invalid_api_key`, reported as `config:`), a missing `RESEND_API_KEY` or `EMAIL_FROM`, and a missing or blank recipient.

The scheduler retries `transient` failures with backoff and abandons the edition on a `permanent` one (see the scheduling spec).

#### Scenario: Rate limited

- GIVEN Resend responds 429 with `Retry-After: 120`
- WHEN the result is classified
- THEN it is `transient` with `retry_after = 120`, and the scheduler's next attempt is no sooner than 120 seconds later (or its normal backoff, if longer)

#### Scenario: Invalid recipient

- GIVEN Resend responds 422 for the recipient address
- WHEN the result is classified
- THEN it is `permanent`

#### Scenario: Unverified sending domain

- GIVEN Resend responds 403 `validation_error` because the sending domain is not verified
- WHEN the result is classified
- THEN it is `permanent` with an `email:` error (not a `config:` API key error)

#### Scenario: Provider not configured

- GIVEN `RESEND_API_KEY` or `EMAIL_FROM` is unset, or there is no recipient
- WHEN a send is attempted
- THEN the result is `permanent` with a `config:` error, and no request is made

---

### Requirement: Idempotent Sends

The system SHALL send every scheduled and manual delivery email with a Resend `Idempotency-Key`, stored on
the delivery (`issue_deliveries.idempotency_key`) when it is marked `sending`. A new key
(`delivery-{id}-{attempts}`) SHALL be used only after Resend answered with an error. When the outcome is
unknown (timeout, network error, unexpected exception or crash after `sending`), the retry SHALL reuse the
stored key. `attempts` counts every failure either way, so retries stay bounded.

#### Scenario: Duplicate submission

- GIVEN a delivery email was accepted by Resend but the outcome was not recorded
- WHEN the same delivery is sent again with the same key within 24 hours
- THEN Resend does not deliver a second email

#### Scenario: Timeout after Resend accepted the email

- GIVEN a send timed out (`outcome_unknown`) although Resend had accepted the email
- WHEN the failure is recorded and the delivery is retried
- THEN `attempts` is incremented but the stored key is kept, so the retry is deduplicated by Resend

#### Scenario: Resend answered with an error

- GIVEN a send failed with an HTTP error response (for example 503)
- WHEN the delivery is retried
- THEN the stored key is cleared and the retry uses `delivery-{id}-{attempts}` with the new attempt number

---

### Requirement: Tracked Delivery Links

When `PUBLIC_API_URL` is set, the system SHALL link scheduled and manual delivery emails to
`{PUBLIC_API_URL}/d/{delivery_id}`, which redirects to the PDF and records the open (see the analytics spec). The
delivery row keeps the real PDF URL. Without `PUBLIC_API_URL`, and for on-demand emails, the email links to the PDF.

---

### Requirement: Safe Email Content

The system SHALL HTML-escape every interpolated value (issue title, PDF link) in the HTML body, and SHALL
send a plain-text alternative with the values as literal text.

#### Scenario: Title containing markup

- GIVEN an issue titled `<img src=x onerror=alert(1)>`
- WHEN its delivery email is rendered
- THEN the title appears as literal text in the HTML body
