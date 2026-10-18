# Analytics Specification

## Purpose

Product analytics and error tracking with PostHog (EU cloud), used to decide whether newsletter2paper is valuable
(activation, retention, conversion to automatic delivery) and to see what breaks. All browser calls go through
`ui/lib/analytics.js`; privacy helpers shared with the Next.js server are in `ui/lib/analyticsPrivacy.js`.

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

### Requirement: Error Tracking

The system SHALL send uncaught browser exceptions and Next.js server request errors (`onRequestError` in
`ui/instrumentation.js`) to PostHog Error tracking. Reporting SHALL NOT throw. The browser's `x-posthog-distinct-id`
and `x-posthog-session-id` headers are client-controlled: they SHALL be used only to attribute an error, and only when
they look like an id (8–64 letters, digits or dashes); otherwise the error is anonymous.

#### Scenario: Forged distinct id

- GIVEN a request whose `x-posthog-distinct-id` is `a@b.co`
- WHEN its route handler throws
- THEN the error is captured without a distinct id
