// Server-side error tracking: exceptions thrown in route handlers, server components and
// middleware go to PostHog Error tracking. No-op without NEXT_PUBLIC_POSTHOG_KEY.
export function register() { }

export async function onRequestError(error, request) {
    const key = process.env.NEXT_PUBLIC_POSTHOG_KEY
    if (!key || process.env.NEXT_RUNTIME !== 'nodejs') return

    const { PostHog } = await import('posthog-node')
    const client = new PostHog(key, {
        host: process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://eu.i.posthog.com',
        flushAt: 1,
        flushInterval: 0,
    })
    // The browser adds this header to same-origin /api calls (tracing_headers in lib/analytics.js).
    const headers = request?.headers || {}
    const distinctId = headers['x-posthog-distinct-id'] || undefined
    const sessionId = headers['x-posthog-session-id']
    try {
        client.captureException(error, distinctId, {
            path: request?.path?.split('?')[0],
            method: request?.method,
            ...(sessionId ? { $session_id: sessionId } : {}),
        })
    } finally {
        await client.shutdown()
    }
}
