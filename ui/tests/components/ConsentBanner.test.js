import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('@/lib/analytics', () => ({
    consent: { status: vi.fn(), accept: vi.fn(), decline: vi.fn() },
}))

import { consent } from '@/lib/analytics'
import ConsentBanner, { OPEN_CONSENT_EVENT } from '@/app/components/ConsentBanner'

describe('ConsentBanner', () => {
    beforeEach(() => {
        consent.status.mockReset()
        consent.accept.mockReset()
        consent.decline.mockReset()
    })

    it('asks while consent is pending', () => {
        consent.status.mockReturnValue('pending')
        render(<ConsentBanner />)
        expect(screen.getByRole('button', { name: 'Accept' })).toBeInTheDocument()
    })

    it.each(['granted', 'denied', null])('stays hidden when the status is %s', (status) => {
        consent.status.mockReturnValue(status)
        render(<ConsentBanner />)
        expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument()
    })

    it('Accept opts in and closes', async () => {
        consent.status.mockReturnValue('pending')
        render(<ConsentBanner />)
        await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
        expect(consent.accept).toHaveBeenCalled()
        expect(consent.decline).not.toHaveBeenCalled()
    })

    it('Decline opts out', async () => {
        consent.status.mockReturnValue('pending')
        render(<ConsentBanner />)
        await userEvent.click(screen.getByRole('button', { name: 'Decline' }))
        expect(consent.decline).toHaveBeenCalled()
        expect(consent.accept).not.toHaveBeenCalled()
    })

    it('reopens from the footer link after a choice', () => {
        consent.status.mockReturnValue('granted')
        render(<ConsentBanner />)
        act(() => window.dispatchEvent(new Event(OPEN_CONSENT_EVENT)))
        expect(screen.getByRole('button', { name: 'Decline' })).toBeInTheDocument()
    })
})
