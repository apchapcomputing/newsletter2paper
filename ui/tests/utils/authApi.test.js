import { describe, it, expect, vi, beforeEach } from 'vitest'

const { getSession } = vi.hoisted(() => ({ getSession: vi.fn() }))
vi.mock('@/lib/supabase', () => ({
    createClient: () => ({ auth: { getSession } }),
}))

import { AuthenticatedAPI } from '@/utils/authApi'

function jsonResponse(body, { ok = true, status = 200, statusText = 'OK', contentType = 'application/json' } = {}) {
    return {
        ok, status, statusText,
        headers: { get: (h) => (h.toLowerCase() === 'content-type' ? contentType : null) },
        json: async () => body,
        text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
    }
}

describe('AuthenticatedAPI', () => {
    let api, fetchMock

    beforeEach(() => {
        getSession.mockResolvedValue({ data: { session: { access_token: 'tok-123' } } })
        fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
        vi.stubGlobal('fetch', fetchMock)
        vi.spyOn(console, 'error').mockImplementation(() => {})
        api = new AuthenticatedAPI()
    })

    describe('auth headers', () => {
        it('sends the bearer token for a signed-in user', async () => {
            await api.get('/issues/1')
            expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer tok-123')
        })

        it('omits Authorization for guests rather than sending "Bearer undefined"', async () => {
            getSession.mockResolvedValue({ data: { session: null } })
            await api.get('/issues/1')
            expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Authorization')
        })

        it('lets a caller override default headers per request', async () => {
            await api.makeRequest('/x', { headers: { 'Content-Type': 'text/plain' } })
            expect(fetchMock.mock.calls[0][1].headers['Content-Type']).toBe('text/plain')
        })
    })

    describe('URL building', () => {
        it('prefixes relative endpoints with the API base and leaves absolute URLs alone', async () => {
            await api.get('/issues')
            await api.makeRequest('https://other.example/y')
            expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/issues')
            expect(fetchMock.mock.calls[1][0]).toBe('https://other.example/y')
        })

        it('appends query params but skips null and undefined ones', async () => {
            await api.get('/articles', { days_back: 7, publication_id: null, start_date: undefined, flag: false })
            const url = new URL(fetchMock.mock.calls[0][0])
            expect(url.searchParams.get('days_back')).toBe('7')
            expect(url.searchParams.get('flag')).toBe('false') // false is a real value
            expect(url.searchParams.has('publication_id')).toBe(false)
            expect(url.searchParams.has('start_date')).toBe(false)
        })
    })

    describe('verbs', () => {
        it.each([
            ['post', 'POST'],
            ['put', 'PUT'],
        ])('%s sends a JSON body with method %s', async (verb, method) => {
            await api[verb]('/issues', { title: 'T' })
            const [, config] = fetchMock.mock.calls[0]
            expect(config.method).toBe(method)
            expect(JSON.parse(config.body)).toEqual({ title: 'T' })
        })

        it('delete has no body', async () => {
            await api.delete('/issues/1')
            const [, config] = fetchMock.mock.calls[0]
            expect(config.method).toBe('DELETE')
            expect(config.body).toBeUndefined()
        })
    })

    describe('responses', () => {
        it('parses JSON bodies', async () => {
            fetchMock.mockResolvedValue(jsonResponse({ a: 1 }))
            expect(await api.get('/x')).toEqual({ a: 1 })
        })

        it('wraps non-JSON success bodies', async () => {
            fetchMock.mockResolvedValue(jsonResponse('plain', { contentType: 'text/plain' }))
            expect(await api.get('/x')).toEqual({ success: true, data: 'plain' })
        })
    })

    describe('errors', () => {
        it.each([
            ['message', { message: 'from message', detail: 'from detail' }, 'from message'],
            ['detail (FastAPI)', { detail: 'from detail' }, 'from detail'],
            ['status when the body has neither', {}, 'HTTP 500'],
        ])('throws using %s', async (_label, body, expected) => {
            fetchMock.mockResolvedValue(jsonResponse(body, { ok: false, status: 500 }))
            await expect(api.get('/x')).rejects.toThrow(expected)
        })

        it('falls back to the status text when the error body is not JSON', async () => {
            const res = jsonResponse({}, { ok: false, status: 502, statusText: 'Bad Gateway' })
            res.json = async () => { throw new SyntaxError('not json') }
            fetchMock.mockResolvedValue(res)
            await expect(api.get('/x')).rejects.toThrow('Bad Gateway')
        })

        it('propagates network failures', async () => {
            fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
            await expect(api.get('/x')).rejects.toThrow('Failed to fetch')
        })
    })
})
