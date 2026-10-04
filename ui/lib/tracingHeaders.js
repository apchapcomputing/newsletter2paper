// The browser adds PostHog's ids to same-origin /api calls (tracing_headers in lib/analytics.js).
// API routes pass them on to the backend so its errors are linked to the visitor's session.
export const TRACING_HEADERS = ['x-posthog-distinct-id', 'x-posthog-session-id']

export function tracingHeaders(request) {
    const out = {}
    for (const name of TRACING_HEADERS) {
        const value = request.headers.get(name)
        if (value) out[name] = value
    }
    return out
}
