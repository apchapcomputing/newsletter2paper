import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const { maybeSingle, eq, select, from } = vi.hoisted(() => {
    const maybeSingle = vi.fn()
    const eq = vi.fn(() => ({ maybeSingle }))
    const select = vi.fn(() => ({ eq }))
    const from = vi.fn(() => ({ select }))
    return { maybeSingle, eq, select, from }
})
vi.mock('@/lib/supabase', () => ({ createClient: () => ({ from }) }))

import ScheduleStatus from '@/app/components/ScheduleStatus'

beforeEach(() => {
    maybeSingle.mockReset()
})

describe('ScheduleStatus', () => {
    it('does not query without an issue and shows nothing', () => {
        const { container } = render(<ScheduleStatus issueId={null} />)
        expect(from).not.toHaveBeenCalled()
        expect(container).toBeEmptyDOMElement()
    })

    it('says the next delivery is being worked out until the scheduler has picked a slot', async () => {
        maybeSingle.mockResolvedValue({ data: { schedule_status: 'idle', next_run_at: null, last_run_error: null }, error: null })
        render(<ScheduleStatus issueId="issue-1" />)
        expect(await screen.findByText(/Working out your next delivery/)).toBeInTheDocument()
        expect(screen.queryByText(/Next delivery:/)).not.toBeInTheDocument()
    })

    it("reads only the scheduler's fields for this issue", async () => {
        maybeSingle.mockResolvedValue({ data: { schedule_status: 'idle', next_run_at: '2026-10-09T13:00:00Z', last_run_error: null }, error: null })
        render(<ScheduleStatus issueId="issue-1" />)
        await screen.findByText(/Next delivery/)
        expect(from).toHaveBeenCalledWith('issues')
        expect(select).toHaveBeenCalledWith('schedule_status, next_run_at, last_run_error')
        expect(eq).toHaveBeenCalledWith('id', 'issue-1')
    })

    it('shows the scheduler’s next delivery, never a client-side estimate', async () => {
        maybeSingle.mockResolvedValue({ data: { schedule_status: 'idle', next_run_at: '2026-10-09T13:00:00Z', last_run_error: null }, error: null })
        render(<ScheduleStatus issueId="issue-1" />)
        await screen.findByText(new RegExp(`Next delivery: ${new Date('2026-10-09T13:00:00Z').toLocaleString().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
        expect(screen.queryByText(/Working out/)).not.toBeInTheDocument()
    })

    it('says when a failed delivery will be retried, with the reason', async () => {
        maybeSingle.mockResolvedValue({ data: { schedule_status: 'failed', next_run_at: '2026-10-05T10:00:00Z', last_run_error: 'email: Resend is unavailable (503: down)' }, error: null })
        render(<ScheduleStatus issueId="issue-1" />)
        expect(await screen.findByText(/Retrying at/)).toBeInTheDocument()
        expect(screen.getByText(/The email couldn't be sent/)).toBeInTheDocument()
        expect(screen.queryByText(/Working out/)).not.toBeInTheDocument()
    })

    it('keeps the last error visible after the edition was given up on', async () => {
        maybeSingle.mockResolvedValue({ data: { schedule_status: 'idle', next_run_at: '2026-10-06T09:00:00Z', last_run_error: 'pdf: renderer timed out (gave up after 5 attempts)' }, error: null })
        render(<ScheduleStatus issueId="issue-1" />)
        expect(await screen.findByRole('alert')).toHaveTextContent("Last delivery failed: We couldn't build the PDF")
        expect(screen.getByText(/Next delivery/)).toBeInTheDocument()
        expect(screen.queryByText(/Retrying at/)).not.toBeInTheDocument()
    })

    it('shows nothing alarming for a healthy issue', async () => {
        maybeSingle.mockResolvedValue({ data: { schedule_status: 'idle', next_run_at: '2026-10-09T13:00:00Z', last_run_error: null }, error: null })
        render(<ScheduleStatus issueId="issue-1" />)
        await screen.findByText(/Next delivery/)
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
        expect(screen.queryByRole('status')).not.toBeInTheDocument()
    })

    it('shows nothing when the query fails instead of breaking the page', async () => {
        maybeSingle.mockResolvedValue({ data: null, error: { message: 'permission denied' } })
        const { container } = render(<ScheduleStatus issueId="issue-1" />)
        await waitFor(() => expect(maybeSingle).toHaveBeenCalled())
        expect(container).toBeEmptyDOMElement()
    })

    it('re-reads when refreshKey changes (e.g. after Send now)', async () => {
        maybeSingle.mockResolvedValue({ data: { schedule_status: 'idle', next_run_at: '2026-10-09T13:00:00Z', last_run_error: null }, error: null })
        const { rerender } = render(<ScheduleStatus issueId="issue-1" refreshKey="idle" />)
        await screen.findByText(/Next delivery/)
        rerender(<ScheduleStatus issueId="issue-1" refreshKey="sent" />)
        await waitFor(() => expect(maybeSingle).toHaveBeenCalledTimes(2))
    })
})
