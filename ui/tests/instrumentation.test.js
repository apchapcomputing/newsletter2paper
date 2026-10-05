import { describe, it, expect, vi, beforeEach } from 'vitest'

const captureException = vi.fn()
const shutdown = vi.fn(async () => { })
const PostHog = vi.fn(() => ({ captureException, shutdown }))
vi.mock('posthog-node', () => ({ PostHog }))

import { onRequestError } from '@/instrumentation'

const request = (headers = {}) => ({ path: '/api/pdf/generate/abc?days_back=7', method: 'POST', headers })
const ID = '0192b3a4-5c6d-7e8f-9a0b-1c2d3e4f5a6b'

describe('onRequestError', () => {
    beforeEach(() => {
        captureException.mockClear()
        shutdown.mockClear()
        PostHog.mockClear()
        vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', 'phc_test')
        vi.stubEnv('NEXT_RUNTIME', 'nodejs')
    })

    it('does nothing without a key', async () => {
        vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', '')
        await onRequestError(new Error('boom'), request())
        expect(PostHog).not.toHaveBeenCalled()
    })

    it('does nothing outside the Node.js runtime', async () => {
        vi.stubEnv('NEXT_RUNTIME', 'edge')
        await onRequestError(new Error('boom'), request())
        expect(PostHog).not.toHaveBeenCalled()
    })

    it('captures with the forwarded ids, the path without its query, and flushes', async () => {
        const error = new Error('boom')
        await onRequestError(error, request({ 'x-posthog-distinct-id': ID, 'x-posthog-session-id': ID }))
        expect(captureException).toHaveBeenCalledWith(error, ID, {
            path: '/api/pdf/generate/abc', method: 'POST', $session_id: ID,
        })
        expect(shutdown).toHaveBeenCalled()
    })

    it('ignores a forged or malformed distinct id', async () => {
        await onRequestError(new Error('boom'), request({ 'x-posthog-distinct-id': 'a@b.co' }))
        expect(captureException.mock.calls[0][1]).toBeUndefined()
        expect(captureException.mock.calls[0][2]).not.toHaveProperty('$session_id')
    })

    it('scrubs exception messages before they are sent', async () => {
        await onRequestError(new Error('boom'), request())
        const { before_send } = PostHog.mock.calls[0][1]
        const out = before_send({ properties: { $exception_list: [{ value: 'fetch https://feed.example/rss failed for a@b.co' }] } })
        expect(out.properties.$exception_list[0].value).toBe('fetch [url] failed for [email]')
    })

    it('never throws, and still flushes, if the SDK fails', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => { })
        captureException.mockImplementationOnce(() => { throw new Error('sdk') })
        shutdown.mockRejectedValueOnce(new Error('network'))
        await expect(onRequestError(new Error('boom'), request())).resolves.toBeUndefined()
        expect(shutdown).toHaveBeenCalled()
    })
})
