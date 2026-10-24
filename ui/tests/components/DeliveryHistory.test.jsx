import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }))
vi.mock('@/lib/apiFetch', () => ({ apiFetch }))

import DeliveryHistory, { describeDelivery } from '@/app/components/DeliveryHistory'

const reply = (body, status = 200) => ({ ok: status < 400, status, json: async () => body })

beforeEach(() => apiFetch.mockReset())

describe('describeDelivery', () => {
    it('summarises a sent edition with its article count and open', () => {
        const line = describeDelivery({ id: 'd1', trigger: 'scheduled', status: 'sent', sent_at: '2026-10-12T09:00:00Z', articles_count: 3, opened_at: '2026-10-12T10:00:00Z' })
        expect(line.summary).toBe('Delivered · 3 articles · opened')
        expect(line.kind).toBe('Scheduled')
        expect(line.error).toBeNull()
    })

    it('uses the singular, and marks manual sends', () => {
        const line = describeDelivery({ id: 'd1', trigger: 'manual', status: 'sent', articles_count: 1 })
        expect(line.summary).toBe('Delivered · 1 article')
        expect(line.kind).toBe('Sent manually')
    })

    it('explains a skipped edition without calling it an error', () => {
        const line = describeDelivery({ id: 'd1', trigger: 'scheduled', status: 'skipped', error: null })
        expect(line.summary).toBe('Skipped (no new articles)')
        expect(line.error).toBeNull()
    })

    it('puts a failure in plain language', () => {
        const line = describeDelivery({ id: 'd1', trigger: 'scheduled', status: 'abandoned', error: 'email: Resend is unavailable (503: down)' })
        expect(line.summary).toBe('Not delivered')
        expect(line.error).toMatch(/The email couldn't be sent/)
    })

    it('tolerates a missing date', () => {
        expect(describeDelivery({ id: 'd1', status: 'pending' }).when).toBe('')
    })
})

describe('DeliveryHistory', () => {
    it('does not call the API without an issue', () => {
        const { container } = render(<DeliveryHistory issueId={null} />)
        expect(apiFetch).not.toHaveBeenCalled()
        expect(container).toBeEmptyDOMElement()
    })

    it('lists the most recent editions', async () => {
        apiFetch.mockResolvedValue(reply({ deliveries: [
            { id: 'd2', trigger: 'scheduled', status: 'sent', sent_at: '2026-10-12T09:00:00Z', articles_count: 4 },
            { id: 'd1', trigger: 'scheduled', status: 'abandoned', scheduled_for: '2026-10-05T09:00:00Z', error: 'pdf: renderer timed out' },
        ] }))
        render(<DeliveryHistory issueId="i1" />)
        expect(await screen.findByText('Delivered · 4 articles')).toBeInTheDocument()
        expect(screen.getByText('Not delivered')).toBeInTheDocument()
        expect(screen.getByText(/We couldn't build the PDF/)).toBeInTheDocument()
        expect(apiFetch).toHaveBeenCalledWith('/api/issues/i1/deliveries?limit=10')
    })

    it('shows nothing before the first edition', async () => {
        apiFetch.mockResolvedValue(reply({ deliveries: [] }))
        const { container } = render(<DeliveryHistory issueId="i1" />)
        await waitFor(() => expect(apiFetch).toHaveBeenCalled())
        expect(container).toBeEmptyDOMElement()
    })

    it('says history is unavailable instead of breaking when the request fails', async () => {
        apiFetch.mockResolvedValue(reply({ error: 'nope' }, 500))
        render(<DeliveryHistory issueId="i1" />)
        expect(await screen.findByText(/Delivery history is unavailable/)).toBeInTheDocument()
    })

    it('re-reads when refreshKey changes', async () => {
        apiFetch.mockResolvedValue(reply({ deliveries: [] }))
        const { rerender } = render(<DeliveryHistory issueId="i1" refreshKey="idle" />)
        await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1))
        rerender(<DeliveryHistory issueId="i1" refreshKey="sent" />)
        await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(2))
    })
})
