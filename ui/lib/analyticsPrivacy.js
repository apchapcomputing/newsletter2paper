// Privacy helpers shared by the browser (lib/analytics.js) and the Next.js server
// (instrumentation.js). Kept free of SDK imports so both can use them.

const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g
const URL = /\b(?:https?|ftp):\/\/[^\s"'<>)\]]+/gi

// Error messages can quote a feed URL or an address ("Failed to fetch https://...").
export function scrubText(value) {
    return typeof value === 'string' ? value.replace(EMAIL, '[email]').replace(URL, '[url]') : value
}

// before_send hook for posthog-js and posthog-node. Property keys are already filtered by
// clean(); this scrubs values: every exception message, the legacy $exception_message, and
// any custom (non-$) string property. $-prefixed SDK properties such as $current_url and stack
// frame file names are left alone, since source maps need the frames.
export function scrubEvent(event) {
    const props = event?.properties
    if (!props) return event
    const out = { ...props }
    if (Array.isArray(out.$exception_list)) {
        out.$exception_list = out.$exception_list.map((exc) => ({ ...exc, value: scrubText(exc.value) }))
    }
    if ('$exception_message' in out) out.$exception_message = scrubText(out.$exception_message)
    for (const [key, value] of Object.entries(out)) {
        if (!key.startsWith('$') && typeof value === 'string') out[key] = scrubText(value)
    }
    return { ...event, properties: out }
}

// The x-posthog-distinct-id header comes from the browser, so it is only used to attribute an
// error, never to authorise anything. Accept only the shape of a PostHog or Supabase id; anything
// else (including the cookieless sentinel) is treated as anonymous.
const DISTINCT_ID = /^[A-Za-z0-9-]{8,64}$/

export function trustedDistinctId(value) {
    return typeof value === 'string' && DISTINCT_ID.test(value) ? value : undefined
}
