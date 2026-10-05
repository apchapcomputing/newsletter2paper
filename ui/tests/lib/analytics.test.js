import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('posthog-js', () => ({
    default: {
        init: vi.fn(),
        capture: vi.fn(),
        identify: vi.fn(),
        reset: vi.fn(),
        captureException: vi.fn(),
        get_distinct_id: vi.fn(() => 'anon-123'),
        get_explicit_consent_status: vi.fn(() => 'pending'),
        opt_in_capturing: vi.fn(),
        opt_out_capturing: vi.fn(),
    },
}))

import posthog from 'posthog-js'
import { initAnalytics, track, identify, reset, captureError, consent, BLOCKED_PROPS } from '@/lib/analytics'

const calls = () => [posthog.init, posthog.capture, posthog.identify, posthog.reset,
    posthog.captureException, posthog.opt_in_capturing, posthog.opt_out_capturing]

describe('analytics without a PostHog key', () => {
    beforeEach(() => vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', ''))

    it('never calls PostHog', () => {
        expect(initAnalytics()).toBe(false)
        track('pdf_generated', { layout: 'essay' })
        identify('user-1')
        reset()
        captureError(new Error('boom'))
        consent.accept()
        consent.decline()
        for (const fn of calls()) expect(fn).not.toHaveBeenCalled()
    })

    it('reports no consent status, so the banner stays hidden', () => {
        expect(consent.status()).toBeNull()
    })
})

describe('analytics with a PostHog key', () => {
    beforeEach(() => {
        vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', 'phc_test')
        for (const fn of calls()) fn.mockClear()
        posthog.get_explicit_consent_status.mockReturnValue('pending')
        reset()
        posthog.reset.mockClear()
    })

    it('initialises through the proxy, cookieless until consent, with exception capture', () => {
        expect(initAnalytics()).toBe(true)
        const [key, config] = posthog.init.mock.calls[0]
        expect(key).toBe('phc_test')
        expect(config).toMatchObject({
            api_host: '/ingest',
            cookieless_mode: 'on_reject',
            capture_exceptions: true,
            disable_session_recording: true,
            person_profiles: 'identified_only',
            tracing_headers: [window.location.host],
        })
    })

    it('sends object_action events with their props', () => {
        track('pdf_generated', { layout: 'essay', publication_count: 3 })
        expect(posthog.capture).toHaveBeenCalledWith('pdf_generated', { layout: 'essay', publication_count: 3 })
    })

    it.each(['pdfGenerated', 'generated', 'PDF_generated', 'pdf-generated', 'pdf_generated_'])(
        'does not send the badly named event %s', (name) => {
            track(name)
            expect(posthog.capture).not.toHaveBeenCalled()
        })

    it('strips PII-prone props before sending', () => {
        const props = Object.fromEntries(BLOCKED_PROPS.map((k) => [k, 'secret']))
        track('issue_created', { ...props, is_guest: true })
        expect(posthog.capture).toHaveBeenCalledWith('issue_created', { is_guest: true })
        captureError(new Error('boom'), { email: 'a@b.c', stage: 'render' })
        expect(posthog.captureException).toHaveBeenCalledWith(expect.any(Error), { stage: 'render' })
    })

    it('identifies by user id only, and skips when already identified', () => {
        posthog.get_explicit_consent_status.mockReturnValue('granted')
        identify('user-1')
        expect(posthog.identify).toHaveBeenCalledWith('user-1')
        posthog.identify.mockClear()
        posthog.get_distinct_id.mockReturnValueOnce('user-1')
        identify('user-1')
        expect(posthog.identify).not.toHaveBeenCalled()
        identify(undefined)
        expect(posthog.identify).not.toHaveBeenCalled()
    })

    it('keeps a visitor without consent anonymous until they accept', () => {
        posthog.get_explicit_consent_status.mockReturnValue('pending')
        identify('user-2')
        expect(posthog.identify).not.toHaveBeenCalled()
        posthog.opt_in_capturing.mockImplementationOnce(() => posthog.get_explicit_consent_status.mockReturnValue('granted'))
        consent.accept()
        expect(posthog.identify).toHaveBeenCalledWith('user-2')
    })

    it('forgets the waiting user on sign-out', () => {
        posthog.get_explicit_consent_status.mockReturnValue('pending')
        identify('user-3')
        reset()
        posthog.opt_in_capturing.mockImplementationOnce(() => posthog.get_explicit_consent_status.mockReturnValue('granted'))
        consent.accept()
        expect(posthog.identify).not.toHaveBeenCalled()
    })

    it('scrubs event values before sending', () => {
        initAnalytics()
        expect(typeof posthog.init.mock.calls[0][1].before_send).toBe('function')
    })

    it('resets on sign-out', () => {
        reset()
        expect(posthog.reset).toHaveBeenCalled()
    })

    it('maps consent choices to opt in and opt out', () => {
        expect(consent.status()).toBe('pending')
        consent.accept()
        expect(posthog.opt_in_capturing).toHaveBeenCalled()
        consent.decline()
        expect(posthog.opt_out_capturing).toHaveBeenCalled()
    })
})
