import { describe, it, expect, vi } from 'vitest'
import { getRssFeedUrl } from '@/utils/rssUtils'

describe('getRssFeedUrl', () => {
    it('asks our API route for the feed of the encoded page URL and returns feed_url', async () => {
        const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ feed_url: 'https://x.substack.com/feed' }) })
        vi.stubGlobal('fetch', fetchMock)

        const result = await getRssFeedUrl('https://x.substack.com/?a=1&b=2')

        expect(fetchMock).toHaveBeenCalledWith('/api/rss/url?webpage_url=https%3A%2F%2Fx.substack.com%2F%3Fa%3D1%26b%3D2')
        expect(result).toBe('https://x.substack.com/feed')
    })

    it('resolves to undefined (not a throw) when the API reports an error, so the caller can show "no feed found"', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {})
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, statusText: 'Not Found' }))
        await expect(getRssFeedUrl('https://nope.example')).resolves.toBeUndefined()
    })

    it('resolves to undefined on network failure', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {})
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
        await expect(getRssFeedUrl('https://x.example')).resolves.toBeUndefined()
    })
})
