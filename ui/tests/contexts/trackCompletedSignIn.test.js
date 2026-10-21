import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/analytics', () => ({ track: vi.fn(), identify: vi.fn(), reset: vi.fn() }))
vi.mock('@/lib/supabase', () => ({ createClient: vi.fn() }))

import { track } from '@/lib/analytics'
import { trackCompletedSignIn } from '@/contexts/useAuth'

const user = (ageMs, provider = 'google') => ({
    id: 'user-1',
    created_at: new Date(Date.now() - ageMs).toISOString(),
    app_metadata: { provider },
})

describe('trackCompletedSignIn', () => {
    beforeEach(() => {
        track.mockClear()
        window.history.replaceState(null, '', '/')
    })

    it('records a new account as signup_completed and removes the flag', () => {
        window.history.replaceState(null, '', '/?signed_in=1&tab=x#top')
        trackCompletedSignIn(user(60 * 1000))
        expect(track).toHaveBeenCalledWith('signup_completed', { method: 'google' })
        expect(window.location.search).toBe('?tab=x')
        expect(window.location.hash).toBe('#top')
    })

    it('records an existing account as signed_in', () => {
        window.history.replaceState(null, '', '/?signed_in=1')
        trackCompletedSignIn(user(30 * 24 * 3600 * 1000, 'email'))
        expect(track).toHaveBeenCalledWith('signed_in', { method: 'email' })
    })

    it('does nothing on a session restore without the flag', () => {
        trackCompletedSignIn(user(1000))
        expect(track).not.toHaveBeenCalled()
    })

    it('fires once even if called again', () => {
        window.history.replaceState(null, '', '/?signed_in=1')
        trackCompletedSignIn(user(1000))
        trackCompletedSignIn(user(1000))
        expect(track).toHaveBeenCalledTimes(1)
    })
})
