# PostHog setup

Configuration done in the PostHog UI, which the code can't express. The event catalogue is in `spec.md`.

## PMF survey (configured in PostHog, no code)

Create a survey under Surveys, set to Popover:

1. "How would you feel if you could no longer use newsletter2paper?" Single choice: Very disappointed / Somewhat disappointed / Not disappointed.
2. "What is the main benefit you get from newsletter2paper?" Open text, optional.
3. "Could we talk for 15 minutes about how you use it? Leave an email if so." Open text, optional. Answers stay in PostHog survey responses; never copy them into event properties.

**Display conditions:** people who have done `pdf_generated` at least twice, or `auto_send_enabled` at least once. Show once per person, after a 5 second delay. A survey can only remember that it was shown when the visitor accepted the consent banner, so cookieless visitors won't see it.

**Reading it:** if 40% or more answer "Very disappointed", that's the usual product/market-fit benchmark (Sean Ellis). Treat it as a rule of thumb and only trust it after about 40 responses.
