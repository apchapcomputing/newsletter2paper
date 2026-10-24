# Email Delivery Specification

## Purpose

Sending newspaper PDF links through Resend (`services/email_service.py`), for scheduled and manual
deliveries and for on-demand generation, plus recipient verification and one-click unsubscribe
(`services/verification.py`, `routers/email_links.py`).

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

---

### Requirement: Recipient Verification

Scheduled mail SHALL go only to an address that is verified: confirmed through an emailed link, or equal
to the issue owner's account email (checked by Supabase Auth). `issues.target_email_verified_at` records
it and is cleared whenever `target_email` changes (unless the same statement sets it).

- `POST /issues/{id}/target-email/verify` (owner only) emails a confirmation link. Capped per issue (3 an hour), per address (3 an hour across all issues) and per account (10 an hour), atomically with the insert (`issue_email_verification`); 429 beyond that.
  It returns `verified: true` without sending when the address is already verified.
- The link opens `GET /email/verify?token=`, which only shows a page. The page's button sends `POST /email/verify?token=`, which verifies the address. Opening the link never verifies, so mail scanners that prefetch links cannot.
- Tokens are random, single-use, expire after 24 hours and are stored as SHA-256 hashes (`email_verifications`, backend-only). A token is refused when the address changed after it was issued.
- A database trigger (`enforce_recipient_verification`) refuses `auto_send = true` for an unverified address when the write comes from a browser role (`anon`, `authenticated`; error `recipient_not_verified`), because the browser writes `issues` directly. The API answers 422 for the same case, and the scheduler records an unconfirmed address as a permanent `config:` failure.
- Changing the address of an issue with `auto_send` on through the API turns `auto_send` off until the new address is confirmed.
- Every send to `target_email` needs a verified address, not only scheduled ones: Send now answers 422 (and the scheduler records a permanent `config:` failure for a manual delivery), and on-demand generation (`POST /pdf/generate/{id}`) still returns the PDF but reports `email_sent: false` with `email_error: "config: the delivery address has not been confirmed"`.
- An owner may set `target_email` to any address, from the browser as well as the API (policy `issues_owner_update`). New issues are inserted with the account email and then updated, since an unlinked row is only visible to its creator through that address. A third-party address starts unverified.

#### Scenario: Enabling delivery to a friend's address

- GIVEN an owner whose issue's `target_email` is not their account email
- WHEN they enable `auto_send` before confirming
- THEN the API answers 422 and the issue is unchanged
- AND after the friend confirms the link, enabling succeeds

#### Scenario: A mail scanner opens the link

- GIVEN a confirmation email whose link is opened by an automated scanner
- WHEN the scanner issues `GET /email/verify?token=...`
- THEN a page with a Confirm button is returned and the address stays unverified

---

### Requirement: Unsubscribe

Scheduled delivery emails SHALL carry `List-Unsubscribe: <{PUBLIC_API_URL}/u/{unsubscribe_token}>` and
`List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058) and a footer link, when `PUBLIC_API_URL` is set.
`POST /u/{token}` turns `auto_send` off for that issue; `GET /u/{token}` only shows a confirmation button.
`issues.unsubscribe_token` is a per-issue random secret that the API never returns.

