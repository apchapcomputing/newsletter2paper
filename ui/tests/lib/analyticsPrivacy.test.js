import { describe, it, expect } from 'vitest'
import { scrubEvent, scrubText, trustedDistinctId } from '@/lib/analyticsPrivacy'

describe('scrubText', () => {
    it('replaces emails and URLs', () => {
        expect(scrubText('Failed to fetch https://news.example.com/feed?x=1 for jo@example.com'))
            .toBe('Failed to fetch [url] for [email]')
    })

    it('leaves non-strings alone', () => {
        expect(scrubText(3)).toBe(3)
        expect(scrubText(undefined)).toBeUndefined()
    })
})

describe('scrubEvent', () => {
    it('scrubs exception messages but keeps stack frames for source maps', () => {
        const frames = [{ filename: 'https://app.example/_next/static/chunks/a.js', lineno: 1 }]
        const event = {
            event: '$exception',
            properties: {
                $exception_list: [{ type: 'TypeError', value: 'bad feed https://x.substack.com/feed', stacktrace: { type: 'raw', frames } }],
                $exception_message: 'bad feed https://x.substack.com/feed',
                $current_url: 'https://app.example/?signed_in=1',
            },
        }
        const out = scrubEvent(event)
        expect(out.properties.$exception_list[0].value).toBe('bad feed [url]')
        expect(out.properties.$exception_list[0].stacktrace.frames).toBe(frames)
        expect(out.properties.$exception_message).toBe('bad feed [url]')
        expect(out.properties.$current_url).toBe('https://app.example/?signed_in=1')
        expect(event.properties.$exception_message).toBe('bad feed https://x.substack.com/feed') // not mutated
    })

    it('scrubs custom string properties', () => {
        expect(scrubEvent({ properties: { note: 'mail me at a@b.co', count: 2 } }).properties)
            .toEqual({ note: 'mail me at [email]', count: 2 })
    })

    it('passes through dropped and property-less events', () => {
        expect(scrubEvent(null)).toBeNull()
        expect(scrubEvent({ event: 'x' })).toEqual({ event: 'x' })
    })
})

describe('trustedDistinctId', () => {
    it.each([
        '0192b3a4-5c6d-7e8f-9a0b-1c2d3e4f5a6b',
        'd1c3a6e2-1f4b-4c8e-9a2d-5b6c7d8e9f01',
    ])('accepts id-shaped value %s', (id) => {
        expect(trustedDistinctId(id)).toBe(id)
    })

    it.each([undefined, '', 'short', '$posthog_cookieless', 'a@b.co', 'x'.repeat(65), '<script>', 'id with spaces'])(
        'rejects %s', (value) => {
            expect(trustedDistinctId(value)).toBeUndefined()
        })
})
