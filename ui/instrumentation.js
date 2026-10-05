// Server-side error tracking: exceptions thrown in route handlers, server components and
// middleware go to PostHog Error tracking. No-op without NEXT_PUBLIC_POSTHOG_KEY.
import { scrubEvent, trustedDistinctId } from './lib/analyticsPrivacy'

export function register() { }

export async function onRequestError(error, request) {
    const key = process.env.NEXT_PUBLIC_POSTHOG_KEY
    if (!key || process.env.NEXT_RUNTIME !== 'nodejs') return

    const { PostHog } = await import('posthog-node')
    const client = new PostHog(key, {
        host: process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://eu.i.posthog.com',
        flushAt: 1,
        flushInterval: 0,
        // Exception messages can quote feed URLs or addresses.
        before_send: scrubEvent,
    })
    // Sent by the browser on same-origin /api calls (tracing_headers in lib/analytics.js).
    // Client-controlled: used only to attribute the error, and only if it looks like an id.
    const headers = request?.headers || {}
    const distinctId = trustedDistinctId(headers['x-posthog-distinct-id'])
    const sessionId = trustedDistinctId(headers['x-posthog-session-id'])
    // Reporting must never turn into a second error inside Next's error handling.
    try {
        client.captureException(error, distinctId, {
            path: request?.path?.split('?')[0],
            method: request?.method,
            ...(sessionId ? { $session_id: sessionId } : {}),
        })
    } catch (e) {
        console.error('PostHog error capture failed:', e)
    } finally {
        await client.shutdown().catch(() => { })
    }
}
