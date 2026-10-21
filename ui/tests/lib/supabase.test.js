import { describe, it, expect, vi } from 'vitest'

const createBrowserClient = vi.fn(() => ({}))
vi.mock('@supabase/ssr', () => ({ createBrowserClient }))

describe('createClient', () => {
    it('wires the guest token fetch into the Supabase client', async () => {
        const { createClient } = await import('@/lib/supabase')
        createClient()
        const options = createBrowserClient.mock.calls[0][2]
        expect(typeof options.global.fetch).toBe('function')

        const base = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}'))
        localStorage.setItem('guestSessionId', 'guest_xyz')
        await options.global.fetch('https://x.test/rest/v1/issues')
        expect(base.mock.calls[0][1].headers.get('x-guest-token')).toBe('guest_xyz')
        base.mockRestore()
    })
})
