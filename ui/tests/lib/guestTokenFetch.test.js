import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createGuestTokenFetch, GUEST_TOKEN_HEADER, GUEST_TOKEN_STORAGE_KEY } from '@/lib/guestTokenFetch'

describe('createGuestTokenFetch', () => {
    let baseFetch

    beforeEach(() => {
        localStorage.clear()
        baseFetch = vi.fn().mockResolvedValue(new Response('{}'))
    })

    afterEach(() => vi.restoreAllMocks())

    it('passes the request through untouched when there is no guest token', async () => {
        const init = { method: 'GET', headers: { apikey: 'k' } }
        await createGuestTokenFetch(baseFetch)('https://x.test/rest/v1/issues', init)
        expect(baseFetch).toHaveBeenCalledWith('https://x.test/rest/v1/issues', init)
    })

    it('adds the x-guest-token header and keeps existing headers', async () => {
        localStorage.setItem(GUEST_TOKEN_STORAGE_KEY, 'guest_abc')
        await createGuestTokenFetch(baseFetch)('https://x.test/rest/v1/issues', {
            method: 'POST',
            headers: { apikey: 'k', Authorization: 'Bearer jwt' },
        })
        const [, init] = baseFetch.mock.calls[0]
        expect(init.method).toBe('POST')
        expect(init.headers.get(GUEST_TOKEN_HEADER)).toBe('guest_abc')
        expect(init.headers.get('apikey')).toBe('k')
        expect(init.headers.get('Authorization')).toBe('Bearer jwt')
    })

    it('keeps headers carried by a Request object', async () => {
        localStorage.setItem(GUEST_TOKEN_STORAGE_KEY, 'guest_abc')
        const req = new Request('https://x.test/rest/v1/issues', { headers: { apikey: 'k' } })
        await createGuestTokenFetch(baseFetch)(req)
        const [, init] = baseFetch.mock.calls[0]
        expect(init.headers.get('apikey')).toBe('k')
        expect(init.headers.get(GUEST_TOKEN_HEADER)).toBe('guest_abc')
    })

    it('reads the token on every request, so a token created later is used', async () => {
        const f = createGuestTokenFetch(baseFetch)
        await f('https://x.test/a')
        localStorage.setItem(GUEST_TOKEN_STORAGE_KEY, 'late')
        await f('https://x.test/b')
        expect(baseFetch.mock.calls[0][1].headers).toBeUndefined()
        expect(baseFetch.mock.calls[1][1].headers.get(GUEST_TOKEN_HEADER)).toBe('late')
    })

    it('does not send a stale token after it is cleared (sign-out)', async () => {
        localStorage.setItem(GUEST_TOKEN_STORAGE_KEY, 'guest_abc')
        const f = createGuestTokenFetch(baseFetch)
        localStorage.removeItem(GUEST_TOKEN_STORAGE_KEY)
        await f('https://x.test/a')
        expect(baseFetch.mock.calls[0][1].headers).toBeUndefined()
    })

    it('falls back to a plain request when localStorage throws', async () => {
        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
        await createGuestTokenFetch(baseFetch)('https://x.test/a')
        expect(baseFetch).toHaveBeenCalledTimes(1)
    })
})
