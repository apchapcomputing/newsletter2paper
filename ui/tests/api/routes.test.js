import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.stubEnv('NEXT_PUBLIC_API_URL', 'http://backend.test')

const upstream = (body, { ok = true, status = 200 } = {}) => ({
    ok, status,
    json: async () => body,
    text: async () => JSON.stringify(body),
})

let fetchMock
beforeEach(() => {
    vi.resetModules()
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'http://backend.test')
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(console, 'error').mockImplementation(() => {})
})

const req = (url, init) => new Request(url, init)

describe('GET /api/rss/url', () => {
    const load = async () => (await import('@/app/api/rss/url/route.js')).GET

    it('requires webpage_url', async () => {
        const res = await (await load())(req('http://app/api/rss/url'))
        expect(res.status).toBe(400)
        expect(fetchMock).not.toHaveBeenCalled()
    })

    it('forwards the encoded URL to the backend and returns its payload', async () => {
        fetchMock.mockResolvedValue(upstream({ feed_url: 'https://x/feed' }))

        const res = await (await load())(req('http://app/api/rss/url?webpage_url=' + encodeURIComponent('https://x.com/?a=1&b=2')))

        expect(fetchMock.mock.calls[0][0]).toBe('http://backend.test/rss/url?webpage_url=https%3A%2F%2Fx.com%2F%3Fa%3D1%26b%3D2')
        expect(await res.json()).toEqual({ feed_url: 'https://x/feed' })
    })

    it('surfaces the backend’s error detail with the backend’s status', async () => {
        fetchMock.mockResolvedValue(upstream({ detail: 'No RSS feed found' }, { ok: false, status: 404 }))
        const res = await (await load())(req('http://app/api/rss/url?webpage_url=https://x.com'))
        expect(res.status).toBe(404)
        expect(await res.json()).toEqual({ error: 'No RSS feed found' })
    })

    it('returns 500 when the backend is unreachable', async () => {
        fetchMock.mockRejectedValue(new Error('ECONNREFUSED'))
        const res = await (await load())(req('http://app/api/rss/url?webpage_url=https://x.com'))
        expect(res.status).toBe(500)
    })
})

describe('GET /api/substack/search', () => {
    const load = async () => (await import('@/app/api/substack/search/route.js')).GET

    it('requires a query', async () => {
        expect((await (await load())(req('http://app/api/substack/search'))).status).toBe(400)
    })

    it('proxies Substack’s search with an encoded query and a descriptive user agent', async () => {
        fetchMock.mockResolvedValue(upstream({ results: [1] }))

        const res = await (await load())(req('http://app/api/substack/search?query=a%20b%26c'))

        const [url, init] = fetchMock.mock.calls[0]
        expect(url).toBe('https://substack.com/api/v1/platform/search?query=a%20b%26c')
        expect(init.headers['User-Agent']).toContain('Newsletter2Paper')
        expect(await res.json()).toEqual({ results: [1] })
    })

    it('reports an upstream failure as a 500 with the reason', async () => {
        fetchMock.mockResolvedValue(upstream({}, { ok: false, status: 429 }))
        const res = await (await load())(req('http://app/api/substack/search?query=x'))
        expect(res.status).toBe(500)
        const body = await res.json()
        expect(body.error).toBe('Failed to search Substack')
        expect(body.details).toContain('429')
    })
})

describe('POST /api/pdf/generate/[issueId]', () => {
    const load = async () => (await import('@/app/api/pdf/generate/[issueId]/route.js')).POST
    const call = async (query = '') => {
        const POST = await load()
        return POST(req('http://app/api/pdf/generate/abc' + query, { method: 'POST' }), { params: Promise.resolve({ issueId: 'abc' }) })
    }
    const backendParams = () => new URL(fetchMock.mock.calls[0][0]).searchParams

    beforeEach(() => {
        fetchMock.mockResolvedValue(upstream({ pdf_url: 'https://pdf', issue_info: { id: 'abc' }, articles_count: 3, email_sent: true }))
    })

    it('targets the backend generate endpoint for the issue with safe defaults', async () => {
        await call()
        expect(fetchMock.mock.calls[0][0]).toMatch(/^http:\/\/backend\.test\/pdf\/generate\/abc\?/)
        expect(fetchMock.mock.calls[0][1].method).toBe('POST')
        const p = backendParams()
        expect(p.get('days_back')).toBe('7')
        expect(p.get('max_articles_per_publication')).toBe('5')
        expect(p.get('keep_html')).toBe('false')
    })

    it('does not override the issue’s saved layout / image settings unless the caller passes them', async () => {
        await call()
        expect(backendParams().has('layout_type')).toBe(false)
        expect(backendParams().has('remove_images')).toBe(false)
    })

    it('forwards explicit overrides, including remove_images=false', async () => {
        await call('?layout_type=essay&remove_images=false&days_back=30&start_date=2026-03-01&end_date=2026-03-07')
        const p = backendParams()
        expect(p.get('layout_type')).toBe('essay')
        expect(p.get('remove_images')).toBe('false')
        expect(p.get('days_back')).toBe('30')
        expect(p.get('start_date')).toBe('2026-03-01')
        expect(p.get('end_date')).toBe('2026-03-07')
    })

    it('returns the fields the UI uses on success', async () => {
        const res = await call()
        expect(res.status).toBe(200)
        expect(await res.json()).toMatchObject({
            success: true, message: 'PDF generated successfully',
            pdf_url: 'https://pdf', issue_info: { id: 'abc' }, articles_count: 3,
        })
    })

    it('maps a backend failure to the same status with the backend’s detail', async () => {
        fetchMock.mockResolvedValue(upstream({ detail: 'No articles found for issue' }, { ok: false, status: 404 }))
        const res = await call()
        expect(res.status).toBe(404)
        const body = await res.json()
        expect(body.success).toBe(false)
        expect(body.message).toBe('No articles found for issue')
    })

    it('returns a 500 with success:false when the backend is unreachable', async () => {
        fetchMock.mockRejectedValue(new Error('down'))
        const res = await call()
        expect(res.status).toBe(500)
        expect((await res.json()).success).toBe(false)
    })
})

describe('POST /api/issues/[issueId]/send-now', () => {
    const call = async (headers = {}) => {
        const { POST } = await import('@/app/api/issues/[issueId]/send-now/route.js')
        return POST(req('http://app/api/issues/abc/send-now', { method: 'POST', headers }), { params: Promise.resolve({ issueId: 'abc' }) })
    }

    it('rejects callers without a session before reaching the backend', async () => {
        const res = await call()
        expect(res.status).toBe(401)
        expect(fetchMock).not.toHaveBeenCalled()
    })

    it('forwards the caller’s bearer token to the backend', async () => {
        fetchMock.mockResolvedValue(upstream({ success: true }, { status: 202 }))
        const res = await call({ Authorization: 'Bearer tok' })
        expect(fetchMock.mock.calls[0][0]).toBe('http://backend.test/issues/abc/send-now')
        expect(fetchMock.mock.calls[0][1].headers).toEqual({ Authorization: 'Bearer tok' })
        expect(res.status).toBe(202)
    })

    it('passes through the backend’s cooldown error', async () => {
        fetchMock.mockResolvedValue(upstream({ detail: 'This issue was sent recently; try again in 5 min' }, { ok: false, status: 429 }))
        const res = await call({ Authorization: 'Bearer tok' })
        expect(res.status).toBe(429)
        expect((await res.json()).error).toMatch(/sent recently/)
    })
})
