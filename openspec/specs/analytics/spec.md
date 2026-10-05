# Analytics Specification

## Purpose

Product analytics and error tracking with PostHog (EU cloud), used to decide whether newsletter2paper is valuable
(activation, retention, conversion to automatic delivery) and to see what breaks. All browser calls go through
`ui/lib/analytics.js`; privacy helpers shared with the Next.js server are in `ui/lib/analyticsPrivacy.js`. The PostHog-side setup (survey, dashboards, alerts) is in `posthog-setup.md`.

---

## Requirements

### Requirement: Privacy-Preserving Capture

The system SHALL NOT send email addresses, article text, feed URLs or issue titles to PostHog. The wrapper SHALL drop
the properties `email`, `target_email`, `url`, `feed_url`, `title`, `query` and `html`, and SHALL drop events whose
names are not `object_action` snake_case. Before sending, every event SHALL have emails and URLs replaced in
exception messages and in custom (non-`$`) string properties (`scrubEvent`, the SDKs' `before_send`). Stack frames
are kept so source maps work. People SHALL be identified by Supabase user id only. Without
`NEXT_PUBLIC_POSTHOG_KEY` every analytics call SHALL be a no-op.

#### Scenario: Blocked property

- GIVEN a `track('issue_created', { title: 'My paper', is_guest: true })` call
- WHEN it is sent
- THEN PostHog receives `issue_created` with `{ is_guest: true }` only

#### Scenario: Error message quoting a feed

- GIVEN an exception `Failed to fetch https://x.substack.com/feed`
- WHEN it is captured in the browser or by `onRequestError`
- THEN Error tracking receives the message `Failed to fetch [url]`, with the stack frames intact

---

### Requirement: Consent

The system SHALL store no analytics identifier in the browser until the visitor accepts the consent banner. Until then,
and after a decline, events SHALL be sent in PostHog cookieless mode (`cookieless_mode: 'on_reject'`) and a signed-in
visitor SHALL NOT be identified; if they accept later, they are identified at that point. The footer's "Privacy
choices" link SHALL reopen the banner.

#### Scenario: Visitor declines

- GIVEN a first-time visitor
- WHEN they click Decline
- THEN no `ph_*` cookie or localStorage entry is written, and pageviews are still counted cookieless

#### Scenario: Signed-in visitor accepts later

- GIVEN a signed-in user who has not answered the banner
- WHEN they load the page, then click Accept
- THEN no `$identify` is sent on load, and one is sent with their user id on Accept

---

### Requirement: Sign-in Events Fire Once

The system SHALL record `signup_completed` (account created under 10 minutes ago) or `signed_in` once per completed
sign-in, using the `signed_in=1` flag that `/auth/callback` adds to the redirect, and SHALL NOT record it on a session
restore.

#### Scenario: Returning user reloads the page

- GIVEN a signed-in user with an existing session
- WHEN the page reloads
- THEN no `signed_in` event is recorded

---

### Requirement: Error Tracking

The system SHALL send uncaught browser exceptions and Next.js server request errors (`onRequestError` in
`ui/instrumentation.js`) to PostHog Error tracking, and SHALL send PDF generation failures other than validation
errors with their `error_type`. The API SHALL send unhandled exceptions, Go render failures, scheduler failures and a
scheduler that fails to start (`services/analytics_service.py`), with emails and URLs scrubbed from exception messages.
Reporting SHALL NOT throw. The Next.js API routes SHALL forward the browser's `x-posthog-distinct-id` and
`x-posthog-session-id` headers to the API, and no other browser headers. These headers are client-controlled: the UI
server and the API SHALL use them only to attribute an error, and only when they look like an id (8–64 letters,
digits or dashes); otherwise the error is anonymous.

#### Scenario: Forged distinct id

- GIVEN a request whose `x-posthog-distinct-id` is `a@b.co`
- WHEN its route handler throws
- THEN the error is captured without a distinct id

#### Scenario: Guest's PDF render fails

- GIVEN a guest generates a PDF and the Go renderer fails
- WHEN the API returns 400
- THEN Error tracking has a `PDFGenerationError` (message scrubbed) with the guest's distinct id, `issue_id`, `layout` and `stage: render`

---

### Requirement: Server-Side Delivery Events

The scheduler SHALL record `delivery_sent`, `delivery_failed` and `delivery_skipped` after the delivery's fenced write
succeeds (a run that lost its claim records nothing), keyed by the issue owner's user id (`user_issues`), or
`issue:<id>` for an issue without an owner. Events SHALL NOT include the error message or recipient; failures carry
`error_kind`, `error_category` (the `email`/`config`/`pdf`/`unexpected error` prefix) and `final`.

#### Scenario: Permanent email failure

- GIVEN Resend rejects a scheduled delivery as permanent
- WHEN the edition is abandoned
- THEN `delivery_failed` is recorded with `final: true`, `error_kind: permanent`, `error_category: email` and no error text

---

### Requirement: Edition Opens

When `PUBLIC_API_URL` is set, scheduled and manual delivery emails SHALL link to `{PUBLIC_API_URL}/d/{delivery_id}`
(the same link on every attempt, so the idempotency key's payload doesn't change). The link SHALL redirect (302) to the
delivery's PDF, record `edition_opened`, and set `issue_deliveries.opened_at` on the first open. An open within 30
seconds of sending SHALL be flagged `likely_scanner` and SHALL NOT set `opened_at`. On-demand emails link to the PDF
directly.

#### Scenario: Mail scanner prefetch

- GIVEN a delivery sent 5 seconds ago
- WHEN its link is fetched
- THEN the request is redirected to the PDF, `edition_opened` has `likely_scanner: true`, and `opened_at` stays NULL

#### Scenario: Unknown link

- GIVEN a delivery id that does not exist or was not sent
- WHEN `/d/{id}` is requested
- THEN the API returns 404

---

### Requirement: Fake Doors

The system SHALL render a fake-door button only while its PostHog flag (`fake-door-<feature>`, underscores as dashes)
is on, SHALL record `fake_door_clicked` and `early_access_requested`, and SHALL NOT collect an email address in the
dialog (signed-in users are reachable through their account; guests are asked to sign in).

---

### Requirement: Session Replay Needs Consent

The system SHALL record sessions only for visitors who accepted the consent banner, with all inputs masked, and SHALL
stop recording when the visitor declines.

---

## Event Catalogue

Names follow `object_action`, snake_case. Never send emails, article text, feed URLs or issue titles.

| Event | Sent from | Properties |
|---|---|---|
| `$pageview`, `$exception` | posthog-js automatically | |
| `publication_added` | `SearchModal`, `AddUrlModal` | `source`: `search` or `url` |
| `issue_created` | `useNewsletterConfig` (first save of a new issue; auto-saves aren't counted) | `is_guest` |
| `pdf_generate_clicked` | `app/page.js` `handleGeneratePdf` | `layout`, `frequency`, `publication_count`, `is_guest` |
| `pdf_generated` | same | the above, plus `duration_ms` |
| `pdf_generate_failed` | same (also sent to Error tracking unless it's a validation error) | the above, plus `error_type`: `validation`, `network`, `backend_4xx`, `backend_5xx` or `bad_response` |
| `auth_modal_opened` | `AuthModal` | `trigger`: `header` or `guest_banner` |
| `signup_started` | `useAuth` sign-in functions (magic link or OAuth) | `method` |
| `signup_completed` / `signed_in` | `useAuth.trackCompletedSignIn`, once per sign-in (the auth callback adds `?signed_in=1`). An account created less than 10 minutes ago counts as a signup. | `method` |
| `auto_send_enabled` / `auto_send_disabled` | `useNewsletterConfig.updateAutoSend` | `frequency` |
| `send_now_clicked` | `ConfigureNewspaper` | |
| `fake_door_clicked` | `FakeDoor` (only rendered while its flag is on) | `feature`, `is_guest` |
| `early_access_requested` | `FakeDoor` dialog | `feature`, `is_guest` |
| `delivery_sent` | scheduler `_succeed` | `issue_id`, `delivery_id`, `trigger`, `frequency`, `attempts` |
| `delivery_failed` | scheduler `_fail` | the above, plus `error_kind`, `error_category`, `final` |
| `delivery_skipped` | scheduler `_skip` | the above, plus `reason`: `no_articles` |
| `edition_opened` | `GET /d/{delivery_id}` (`routers/deliveries.py`) | `issue_id`, `delivery_id`, `trigger`, `first_open`, `likely_scanner`, `hours_since_sent` |

Server events use the issue owner's Supabase user id (`issue:<id>` for guest issues). People are identified by Supabase user id on sign-in. Guests are anonymous: a stored ID if they accepted the consent banner, cookieless otherwise.
