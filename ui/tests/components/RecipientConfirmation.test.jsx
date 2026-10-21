import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const { apiFetch, track } = vi.hoisted(() => ({ apiFetch: vi.fn(), track: vi.fn() }))
vi.mock('@/lib/apiFetch', () => ({ apiFetch }))
vi.mock('@/lib/analytics', () => ({ track }))

import RecipientConfirmation from '@/app/components/RecipientConfirmation'

const reply = (body, status = 200) => ({ ok: status < 400, status, json: async () => body })

beforeEach(() => {
    apiFetch.mockReset()
    track.mockReset()
})

describe('RecipientConfirmation', () => {
    it('renders nothing for a confirmed address or an empty field', () => {
        const { container, rerender } = render(<RecipientConfirmation issueId="i1" email="a@b.co" saved confirmed />)
        expect(container).toBeEmptyDOMElement()
        rerender(<RecipientConfirmation issueId="i1" email="" saved confirmed={false} />)
        expect(container).toBeEmptyDOMElement()
    })

    it('asks to save the address first when it only exists in the form', () => {
        render(<RecipientConfirmation issueId="i1" email="a@b.co" saved={false} confirmed={false} />)
        expect(screen.getByText(/Save this address/)).toBeInTheDocument()
        expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })

    it('requests the confirmation email and tells the owner where to look', async () => {
        apiFetch.mockResolvedValue(reply({ success: true, verified: false }))
        const onRequested = vi.fn()
        render(<RecipientConfirmation issueId="i1" email="a@b.co" saved confirmed={false} onRequested={onRequested} />)

        fireEvent.click(screen.getByRole('button', { name: 'Send confirmation email' }))

        expect(await screen.findByRole('status')).toHaveTextContent('We sent a confirmation link to a@b.co')
        expect(apiFetch).toHaveBeenCalledWith('/api/issues/i1/target-email/verify', { method: 'POST' })
        expect(track).toHaveBeenCalledWith('recipient_verification_requested')
        expect(onRequested).toHaveBeenCalled()
        expect(screen.getByRole('button', { name: 'Send again' })).toBeInTheDocument()
    })

    it('shows the server’s reason when the request is refused (e.g. too many requests)', async () => {
        apiFetch.mockResolvedValue(reply({ error: 'Too many confirmation emails; try again in an hour' }, 429))
        render(<RecipientConfirmation issueId="i1" email="a@b.co" saved confirmed={false} />)
        fireEvent.click(screen.getByRole('button'))
        expect(await screen.findByRole('alert')).toHaveTextContent('Too many confirmation emails')
        expect(track).not.toHaveBeenCalled()
    })

    it('refreshes quietly when the server says the address is already confirmed', async () => {
        apiFetch.mockResolvedValue(reply({ success: true, verified: true }))
        const onRequested = vi.fn()
        render(<RecipientConfirmation issueId="i1" email="a@b.co" saved confirmed={false} onRequested={onRequested} />)
        fireEvent.click(screen.getByRole('button'))
        await waitFor(() => expect(onRequested).toHaveBeenCalled())
        expect(screen.queryByRole('status')).not.toBeInTheDocument()
    })

    it('copes with an unreachable server', async () => {
        apiFetch.mockRejectedValue(new Error('offline'))
        render(<RecipientConfirmation issueId="i1" email="a@b.co" saved confirmed={false} />)
        fireEvent.click(screen.getByRole('button'))
        expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server')
    })
})
