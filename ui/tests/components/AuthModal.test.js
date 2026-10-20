import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'

vi.mock('@/lib/analytics', () => ({ track: vi.fn() }))
vi.mock('@/contexts/useAuth', () => ({
    useAuth: () => ({ signInWithMagicLink: vi.fn(), signInWithProvider: vi.fn() }),
}))

import { track } from '@/lib/analytics'
import AuthModal from '@/app/components/AuthModal'

describe('AuthModal analytics', () => {
    beforeEach(() => track.mockClear())

    it('records auth_modal_opened with its trigger when opened', () => {
        const { rerender } = render(<AuthModal open={false} onClose={() => { }} trigger="guest_banner" />)
        expect(track).not.toHaveBeenCalled()
        rerender(<AuthModal open onClose={() => { }} trigger="guest_banner" />)
        expect(track).toHaveBeenCalledWith('auth_modal_opened', { trigger: 'guest_banner' })
    })
})
