// The browser adds PostHog's ids to same-origin /api calls (tracing_headers in lib/analytics.js).
// API routes pass them on to the backend so its errors are linked to the visitor's session.
// They are client-controlled, so only id-shaped values are forwarded (attribution only).
import { trustedDistinctId } from './analyticsPrivacy'

export const TRACING_HEADERS = ['x-posthog-distinct-id', 'x-posthog-session-id']

export function tracingHeaders(request) {
    const out = {}
    for (const name of TRACING_HEADERS) {
        const value = trustedDistinctId(request.headers.get(name))
        if (value) out[name] = value
    }
    return out
}
