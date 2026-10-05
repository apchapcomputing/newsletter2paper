// The only module that talks to PostHog. Every function is a no-op when
// NEXT_PUBLIC_POSTHOG_KEY is unset (local dev, vitest), so callers never check.
//
// Event names are object_action in snake_case (pdf_generated, issue_created).
// Never send emails, article text, feed URLs or issue titles: BLOCKED_PROPS are
// dropped before anything leaves the browser.
import posthog from 'posthog-js'
import { scrubEvent } from './analyticsPrivacy'

export const BLOCKED_PROPS = ['email', 'target_email', 'url', 'feed_url', 'title', 'query', 'html']
const EVENT_NAME = /^[a-z]+(_[a-z]+)+$/
const isDevelopment = process.env.NODE_ENV === 'development'

// Signed-in user waiting for consent: identify() only links the person after the visitor accepts.
let pendingUserId = null

function enabled() {
    return typeof window !== 'undefined' && Boolean(process.env.NEXT_PUBLIC_POSTHOG_KEY)
}

function warn(...args) {
    if (isDevelopment) console.warn('[analytics]', ...args)
}

function clean(props = {}) {
    const out = {}
    for (const [key, value] of Object.entries(props)) {
        if (BLOCKED_PROPS.includes(key)) {
            warn(`dropped blocked property "${key}"`)
            continue
        }
        out[key] = value
    }
    return out
}

// Called once from instrumentation-client.js, before the app hydrates.
export function initAnalytics() {
    if (!enabled()) return false
    posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
        api_host: '/ingest', // reverse proxy in next.config.mjs, so ad blockers drop fewer events
        ui_host: 'https://eu.posthog.com',
        defaults: '2026-08-30', // includes capture_pageview: 'history_change' for App Router navigations
        // No cookies or storage until the visitor accepts the banner; before that (and after
        // a decline) events are sent in cookieless mode.
        cookieless_mode: 'on_reject',
        person_profiles: 'identified_only',
        capture_exceptions: true,
        // Replay only for visitors who accepted the banner (started below and in consent.accept),
        // with every input masked. It also has to be enabled in the PostHog project settings.
        disable_session_recording: true,
        session_recording: { maskAllInputs: true },
        loaded: (ph) => {
            if (ph.get_explicit_consent_status() === 'granted') ph.startSessionRecording()
        },
        // Same-origin /api/* calls carry X-POSTHOG-DISTINCT-ID / X-POSTHOG-SESSION-ID so
        // backend errors can be linked to the visitor.
        tracing_headers: [window.location.host],
        // clean() filters property keys; this scrubs emails and URLs out of values, including
        // exception messages.
        before_send: scrubEvent,
    })
    return true
}

export function track(event, props) {
    if (!EVENT_NAME.test(event)) {
        warn(`event "${event}" is not object_action snake_case; not sent`)
        return
    }
    if (!enabled()) return
    posthog.capture(event, clean(props))
}

// User id only; the Supabase id is the person's distinct id. Without consent the visitor stays
// anonymous (cookieless): the id is held here and linked if they accept later.
export function identify(userId) {
    if (!enabled() || !userId) return
    pendingUserId = String(userId)
    if (posthog.get_explicit_consent_status() !== 'granted') return
    if (posthog.get_distinct_id() === pendingUserId) return // session recovery re-fires SIGNED_IN
    posthog.identify(pendingUserId)
}

export function reset() {
    pendingUserId = null
    if (!enabled()) return
    posthog.reset()
}

export function captureError(error, props) {
    if (!enabled()) return
    posthog.captureException(error, clean(props))
}

export const consent = {
    // 'pending' | 'granted' | 'denied', or null when analytics is off (no banner needed).
    status() {
        return enabled() ? posthog.get_explicit_consent_status() : null
    },
    accept() {
        if (!enabled()) return
        posthog.opt_in_capturing()
        if (pendingUserId) identify(pendingUserId)
        posthog.startSessionRecording()
    },
    decline() {
        if (!enabled()) return
        posthog.stopSessionRecording()
        posthog.opt_out_capturing()
    },
}

// Feature flags, used to switch fake doors on and off from PostHog without a deploy.
export function flagEnabled(flag) {
    return enabled() && Boolean(posthog.isFeatureEnabled(flag))
}

export function flagPayload(flag) {
    return enabled() ? (posthog.getFeatureFlagPayload(flag) ?? null) : null
}

// Calls back when flags load or change; returns an unsubscribe function.
export function onFlags(callback) {
    return enabled() ? posthog.onFeatureFlags(callback) : () => { }
}
