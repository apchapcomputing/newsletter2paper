# PostHog setup

Configuration done in the PostHog UI, which the code can't express. The event catalogue is in `spec.md`.

## Environment

| Where | Variables |
|---|---|
| Vercel (UI) | `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST`; optionally `POSTHOG_PERSONAL_API_KEY` and `POSTHOG_PROJECT_ID` for source maps |
| Droplet `.env` (API) | `POSTHOG_API_KEY` (the same project key), `POSTHOG_HOST`, and `PUBLIC_API_URL` (the API's public https URL) once migration `20261007000000_delivery_opened_at.sql` is applied |

## PMF survey (configured in PostHog, no code)

Create a survey under Surveys, set to Popover:

1. "How would you feel if you could no longer use newsletter2paper?" Single choice: Very disappointed / Somewhat disappointed / Not disappointed.
2. "What is the main benefit you get from newsletter2paper?" Open text, optional.
3. "Could we talk for 15 minutes about how you use it? Leave an email if so." Open text, optional. Answers stay in PostHog survey responses; never copy them into event properties.

**Display conditions:** people who have done `pdf_generated` at least twice, or `auto_send_enabled` at least once. Show once per person, after a 5 second delay. A survey can only remember that it was shown when the visitor accepted the consent banner, so cookieless visitors won't see it.

**Reading it:** if 40% or more answer "Very disappointed", that's the usual product/market-fit benchmark (Sean Ellis). Treat it as a rule of thumb and only trust it after about 40 responses.

## Fake doors (feature flags)

Each fake door is hidden until you create its flag, with a release condition of 100% of users. A JSON payload can override the copy, for example `{"label": "Automatic delivery: $4/month. Reserve founder pricing"}`.

| Flag | Where it shows | What it tests |
|---|---|---|
| `fake-door-upgrade-auto-send` | under the auto-send switch (signed-in users) | willingness to pay for automatic delivery, before the Stripe work |
| `fake-door-send-to-ereader` | after a PDF is generated | a "send to Kindle/reMarkable" pivot |
| `fake-door-mail-printed-copy` | after a PDF is generated | a printed-and-mailed product |
| `fake-door-single-article` | after a PDF is generated | adding single articles (the planned paid feature) |

Compare `early_access_requested` per feature against the people who saw it (`pdf_generated` for the post-PDF doors). Switch a door off once you have your answer. A door that's always visible teaches users to ignore it.

## Session replay

Turn on session replay in project settings, with "Mask all inputs" on. Recording starts only for visitors who accepted the banner. Useful playlists:
- sessions with `pdf_generate_failed`
- sessions with `publication_added` but no `pdf_generated`
- first sessions of people who later did `signup_completed`

Watch about ten a week. The free tier allows 5,000 recordings a month.

## Cohorts for outreach

| Cohort | Definition |
|---|---|
| Power users | `pdf_generated` at least 3 times in 30 days, or `auto_send_enabled` and `delivery_sent` in the last 30 days |
| Tried once | `pdf_generated` exactly once, and nothing in the 14 days since |
| Unread editions | `delivery_sent` at least 3 times in 30 days and no `edition_opened` with `likely_scanner = false` |
| Wants a feature | `early_access_requested`, broken down by `feature` |

A signed-in person's distinct id is their Supabase user id. Look up the email in Supabase (`auth.users`) and invite them to a 15-minute call. Guests can't be contacted, except through the survey's "Can we talk?" answer.

## Billing guardrail

In Billing, set a $0 limit on every product until there's revenue. Free tier, per month: 1M events, 5k recordings, 1M flag requests, 1.5k survey responses.

## Dashboard: "Is it valuable?"

Create each insight below and add it to one dashboard. **"Printers"** means people with `pdf_generated` or `delivery_sent`.

| Insight | Type | Definition |
|---|---|---|
| Weekly printers (north star) | Trends | Unique users with `pdf_generated` or `delivery_sent`, weekly |
| Activation | Funnel, 1-day window | `$pageview` → `publication_added` → `pdf_generated` |
| Monetization | Funnel, 30-day window | `pdf_generated` → `signup_completed` → `auto_send_enabled` (add `subscription_started` once Stripe exists) |
| Retention | Retention, weekly | Start: `pdf_generated`. Return: `pdf_generated` or `delivery_sent`. Break down by `is_guest`. Look for a curve that flattens, not one that decays to zero. |
| Edition open rate | Trends, formula | A = `edition_opened` where `first_open = true` and `likely_scanner = false`; B = `delivery_sent`; formula `A / B`, weekly |
| Acquisition | Funnel (activation) | Break down by `$initial_referring_domain`, then by `$initial_utm_source` |
| Repeat use | Trends | Unique users with `pdf_generated` at least 2 times in 30 days |
| PMF survey | Survey results | the survey from the section above |

## Dashboard: "Health"

| Insight | Type | Definition |
|---|---|---|
| Errors | Error tracking | Issues list, sorted by occurrences in the last 7 days (browser, Next server and API, grouped) |
| PDF failure rate | Trends, formula | `pdf_generate_failed` / `pdf_generate_clicked`, daily, broken down by `error_type` |
| Delivery failures | Trends | `delivery_failed` broken down by `error_category` and `final` |
| Deliveries sent | Trends | `delivery_sent` per day |

**Alerts** (Insight → Alerts, notify by email):
- PDF failures: `pdf_generate_failed` count above 5 in an hour.
- Lost editions: `delivery_failed` with `final = true`, count above 0 in a day.
- Scheduler silent: `delivery_sent` count is 0 over a day while any issue has auto-send on. Until the scheduler emits a heartbeat, check this one by hand when it fires; it can fire on a genuinely quiet day.
- Error tracking: turn on email notifications for new issues.

## UTM convention

Tag every link you post or pay for. PostHog reads `utm_*` and the referrer automatically.

| Parameter | Value | Examples |
|---|---|---|
| `utm_source` | channel | `reddit`, `x`, `hn`, `newsletter`, `producthunt` |
| `utm_medium` | `organic` or `paid` | |
| `utm_campaign` | the post or ad | `launch-oct26`, `r-substack-printing` |

Example: `https://newsletter2paper.xyz/?utm_source=reddit&utm_medium=organic&utm_campaign=r-substack-printing`

## Decision guide

Settle these thresholds before you spend on marketing, and review the dashboards for 15 minutes each week. These are common rules of thumb, not laws, and they mean little before about 100 activated users or 40 survey responses.

- **Keep marketing:** at least 40% "very disappointed" on the PMF survey, plus a retention curve that flattens above zero.
- **Activation is fine but nobody comes back:** the core value isn't landing. Read the survey's "main benefit" answers and talk to the "tried once" cohort before deciding to pivot.
- **Activation is poor:** fix onboarding and the landing message before judging the product.
- **Edition open rate is low for auto-send users:** the paid feature isn't valued as delivered. Look at timing, frequency and content before building more features.

## Privacy policy

Add a line along these lines: "We use PostHog (EU) for anonymous product analytics and error reports. With your consent we store an anonymous identifier in your browser; without it, visits are counted without cookies. We never send your email address or newsletter content to analytics."
