import { describe, it, expect, vi } from 'vitest'
import fixture from '../fixtures/susbtack-search.json'
import { searchSubstack } from '@/utils/substackUtils'

function mockSearchResponse(body, { ok = true, status = 200, statusText = 'OK' } = {}) {
    const fetchMock = vi.fn().mockResolvedValue({
        ok, status, statusText,
        json: async () => body,
    })
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
}

const publicationResult = (overrides = {}) => ({
    type: 'publication',
    publication: { name: 'Pub', author_name: 'Ada Writer', subdomain: 'pub', custom_domain: null, subscriber_count_string: '1K', ...overrides },
})
const userResult = (overrides = {}) => ({
    type: 'user',
    user: { name: 'Ada Writer', handle: 'ada', publication_name: 'Ada Letter', subscriber_count_string: '2K', ...overrides },
})

describe('searchSubstack', () => {
    it('does not hit the network for a blank query', async () => {
        const fetchMock = mockSearchResponse({ results: [] })
        expect(await searchSubstack('   ')).toEqual([])
        expect(fetchMock).not.toHaveBeenCalled()
    })

    it('url-encodes the query it sends to our API route', async () => {
        const fetchMock = mockSearchResponse({ results: [] })
        await searchSubstack('a&b c')
        expect(fetchMock).toHaveBeenCalledWith('/api/substack/search?query=a%26b%20c')
    })

    it('maps real Substack search output: every result becomes a usable publication entry', async () => {
        mockSearchResponse(fixture)
        const results = await searchSubstack('young')

        expect(results).toHaveLength(fixture.results.length)
        for (const r of results) {
            expect(r.name).toBeTruthy()
            expect(['user', 'publication']).toContain(r.type)
            // The UI needs something to turn into a feed URL for every row.
            expect(r.domain || r.subdomain).toBeTruthy()
        }
    })

    it('publication results prefer the custom domain over <subdomain>.substack.com', async () => {
        mockSearchResponse({ results: [
            publicationResult({ subdomain: 'young', custom_domain: 'www.youngmoney.co' }),
            publicationResult({ subdomain: 'plain', custom_domain: null }),
        ] })
        const [custom, plain] = await searchSubstack('x')
        expect(custom.domain).toBe('www.youngmoney.co')
        expect(plain.domain).toBe('plain.substack.com')
    })

    it('user results use their handle as the subdomain and the publication name as the title', async () => {
        mockSearchResponse({ results: [userResult()] })
        const [u] = await searchSubstack('x')
        expect(u).toMatchObject({ type: 'user', name: 'Ada Letter', subdomain: 'ada', handle: 'ada', subscribers: '2K' })
    })

    it('falls back to the person’s name, then a placeholder, when a user has no publication name', async () => {
        mockSearchResponse({ results: [userResult({ publication_name: undefined }), userResult({ publication_name: undefined, name: undefined })] })
        const [a, b] = await searchSubstack('x')
        expect(a.name).toBe('Ada Writer')
        expect(b.name).toBe('Unknown Publication')
        expect(b.publisher).toBe('Unknown Publisher')
    })

    it('skips result types it does not understand', async () => {
        mockSearchResponse({ results: [{ type: 'post', post: {} }, publicationResult()] })
        expect(await searchSubstack('x')).toHaveLength(1)
    })

    it('never produces an "undefined.substack.com" domain', async () => {
        mockSearchResponse({ results: [publicationResult({ subdomain: undefined, custom_domain: undefined })] })
        const [p] = await searchSubstack('x')
        expect(p.domain ?? '').not.toContain('undefined')
    })

    describe('publisher name formatting', () => {
        async function publisherFor(name) {
            mockSearchResponse({ results: [publicationResult({ author_name: name })] })
            return (await searchSubstack('x'))[0].publisher
        }

        it('capitalises the first letter of each word', async () => {
            expect(await publisherFor('ada lovelace')).toBe('Ada Lovelace')
        })

        it('keeps nobiliary particles lowercase in the middle of a name', async () => {
            expect(await publisherFor('Ludwig van Beethoven')).toBe('Ludwig van Beethoven')
        })

        it('still capitalises a particle that is the first word (e.g. "Van Jones")', async () => {
            expect(await publisherFor('van jones')).toBe('Van Jones')
        })

        it('preserves intentional internal capitals such as McDonald', async () => {
            expect(await publisherFor('Ronald McDonald')).toBe('Ronald McDonald')
        })

        it('tolerates repeated spaces', async () => {
            expect(await publisherFor('Ada  Lovelace')).toBe('Ada  Lovelace')
        })
    })

    describe('failure handling', () => {
        it('returns an empty list when our API route errors, instead of throwing into the UI', async () => {
            vi.spyOn(console, 'error').mockImplementation(() => {})
            mockSearchResponse({ error: 'Failed to search Substack', details: 'boom' }, { ok: false, status: 500, statusText: 'Server Error' })
            expect(await searchSubstack('x')).toEqual([])
        })

        it('returns an empty list on a network failure', async () => {
            vi.spyOn(console, 'error').mockImplementation(() => {})
            vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
            expect(await searchSubstack('x')).toEqual([])
        })

        it('treats a response without results as no results', async () => {
            mockSearchResponse({})
            expect(await searchSubstack('x')).toEqual([])
        })
    })
})
