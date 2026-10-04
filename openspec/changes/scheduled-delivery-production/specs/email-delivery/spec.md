# Email Delivery Spec Delta: Production-Ready Scheduled Delivery

New domain `email-delivery`: sending newspaper PDFs and owner notifications through Resend.

## ADDED Requirements

### Requirement: Structured Send Result

The system SHALL return a result for every send attempt containing `ok`, `message_id`, `error_kind` (`transient` | `permanent`) and a user-readable `error`. It SHALL NOT report failure as a bare boolean or swallow it in logs.

#### Scenario: Scheduled send fails

- GIVEN Resend rejects a scheduled delivery email
- WHEN the scheduler records the result
- THEN the delivery and `issues.last_run_error` contain an `email:`-prefixed message describing the cause

#### Scenario: On-demand generation reports email outcome

- GIVEN a user generates a PDF on demand for an issue with a verified `target_email`
- WHEN the email send fails
- THEN the response includes `email_sent: false` and `email_error` with the cause, and the PDF response still succeeds

---

### Requirement: Error Classification

The system SHALL classify send failures as follows:

- `transient`: HTTP 429, HTTP 5xx, network errors and timeouts.
- `permanent`: any other HTTP 4xx (for example an invalid address or an unverified sending domain), a missing `RESEND_API_KEY` or `EMAIL_FROM`, and a missing or unverified recipient.

#### Scenario: Rate limited

- GIVEN Resend responds 429 with `Retry-After: 120`
- WHEN the result is classified
- THEN it is `transient`, and the next attempt is no sooner than 120 seconds later

#### Scenario: Invalid recipient

- GIVEN Resend responds 422 for the recipient address
- WHEN the result is classified
- THEN it is `permanent`

#### Scenario: Provider not configured

- GIVEN `RESEND_API_KEY` is unset
- WHEN a send is attempted
- THEN the result is `permanent` with a `config:` error, and no request is made

---

### Requirement: Idempotent Sends

The system SHALL send every delivery email with a Resend `Idempotency-Key` derived from the delivery id and attempt number. The key SHALL be reused unchanged when a send whose outcome is unknown is retried.

#### Scenario: Duplicate submission

- GIVEN a delivery email was accepted by Resend but the outcome was not recorded
- WHEN the same delivery is sent again with the same key within 24 hours
- THEN Resend does not deliver a second email

---

### Requirement: Recipient Verification

The system SHALL send scheduled and manual deliveries only to a `target_email` with `target_email_verified_at` set. An address equal to the owner's confirmed account email SHALL be verified automatically. Any other address SHALL be verified by a single-use link that expires after 24 hours.

#### Scenario: Account email is verified automatically

- GIVEN the owner sets `target_email` to their confirmed account email
- WHEN the change is saved
- THEN `target_email_verified_at` is set

#### Scenario: Other address requires confirmation

- GIVEN the owner sets `target_email` to a different address
- WHEN the change is saved
- THEN `target_email_verified_at` is cleared, and deliveries fail permanently with a `config:` error until the link is confirmed

#### Scenario: Confirmation link

- GIVEN the owner requests `POST /issues/{id}/target-email/verify`
- WHEN the recipient opens the link within 24 hours and the issue's `target_email` has not changed since
- THEN `target_email_verified_at` is set and the token is consumed

#### Scenario: Stale or reused link

- GIVEN a verification token that has expired, been used, or was issued for a different address
- WHEN it is opened
- THEN verification fails with an explanatory page and nothing changes

#### Scenario: Verification requests are rate limited

- GIVEN three verification emails were requested for an issue within the last hour
- WHEN a fourth is requested
- THEN the API returns 429

---

### Requirement: Unsubscribe

The system SHALL include a one-click unsubscribe link and the `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` headers in every delivery email. Unsubscribing SHALL set the issue's `auto_send` to false.

#### Scenario: One-click unsubscribe

- GIVEN a recipient's mail client posts to the `List-Unsubscribe` URL
- WHEN the token matches an issue's `unsubscribe_token`
- THEN `auto_send` becomes false and no further scheduled deliveries are sent

#### Scenario: Unknown token

- GIVEN an unsubscribe request with an unknown token
- WHEN it is processed
- THEN the response is a generic confirmation page and nothing changes

---

### Requirement: Safe Email Content

The system SHALL HTML-escape every user-controlled value (issue title, publication names) interpolated into email bodies, and SHALL send a plain-text alternative.

#### Scenario: Title containing markup

- GIVEN an issue titled `<img src=x onerror=alert(1)>`
- WHEN its delivery email is rendered
- THEN the title appears as literal text in the HTML body
