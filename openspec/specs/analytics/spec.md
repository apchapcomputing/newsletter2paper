# Analytics Specification

## Purpose

Product analytics and error tracking with PostHog (EU cloud), used to decide whether newsletter2paper is valuable
(activation, retention, conversion to automatic delivery) and to see what breaks. All browser calls go through
`ui/lib/analytics.js`. The PostHog-side setup (survey, dashboards, alerts) is in `posthog-setup.md`.

---

## Requirements

### Requirement: Privacy-Preserving Capture

The system SHALL NOT send email addresses, article text, feed URLs or issue titles to PostHog. The wrapper SHALL drop
the properties `email`, `target_email`, `url`, `feed_url`, `title`, `query` and `html`, and SHALL drop events whose
names are not `object_action` snake_case. People SHALL be identified by Supabase user id only. Without
`NEXT_PUBLIC_POSTHOG_KEY` every analytics call SHALL be a no-op.

#### Scenario: Blocked property

- GIVEN a `track('issue_created', { title: 'My paper', is_guest: true })` call
- WHEN it is sent
- THEN PostHog receives `issue_created` with `{ is_guest: true }` only

---

### Requirement: Consent

The system SHALL store no analytics identifier in the browser until the visitor accepts the consent banner. Until then,
and after a decline, events SHALL be sent in PostHog cookieless mode (`cookieless_mode: 'on_reject'`). The footer's
"Privacy choices" link SHALL reopen the banner.

#### Scenario: Visitor declines

- GIVEN a first-time visitor
- WHEN they click Decline
- THEN no `ph_*` cookie or localStorage entry is written, and pageviews are still counted cookieless

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

The system SHALL send uncaught browser exceptions and Next.js server request errors to PostHog Error tracking, and
SHALL send PDF generation failures other than validation errors with their `error_type`.

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

People are identified by Supabase user id on sign-in. Guests are anonymous: a stored ID if they accepted the consent banner, cookieless otherwise.
