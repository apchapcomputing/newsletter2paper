import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
    apiFetch: vi.fn(),
    config: {},
    schedule: { issue: null, refresh: vi.fn(), save: vi.fn() },
    saveIssueToSupabase: vi.fn(),
}))

vi.mock('@/contexts/useNewsletterConfig', () => ({ useNewsletterConfig: () => mocks.config }))
vi.mock('@/contexts/useAuth', () => ({ useAuth: () => ({ session: { access_token: 'tok' } }) }))
vi.mock('@/lib/useIssueSchedule', () => ({ useIssueSchedule: () => mocks.schedule }))
vi.mock('@/lib/analytics', () => ({ track: vi.fn() }))
vi.mock('@/lib/apiFetch', () => ({ apiFetch: (...args) => mocks.apiFetch(...args) }))
vi.mock('@/app/components/FakeDoor', () => ({ default: () => null }))
vi.mock('@/app/components/ScheduleStatus', () => ({ default: () => <div data-testid="status" /> }))

import ConfigureNewspaper from '@/app/components/ConfigureNewspaper'

const base = () => ({
    newspaperTitle: 'T', outputMode: 'essay', frequency: 'weekly', dateFrom: '', dateTo: '',
    targetEmail: 'me@example.com', currentIssueId: 'i1', isAuthenticated: true,
    articleWindow: '7', autoSend: false, autoSendError: null,
    updateTitle: vi.fn(), updateOutputMode: vi.fn(), updateFrequency: vi.fn(), updateDateFrom: vi.fn(),
    updateDateTo: vi.fn(), updateTargetEmail: vi.fn(), updateArticleWindow: vi.fn(), updateAutoSend: vi.fn(),
    saveIssueToSupabase: mocks.saveIssueToSupabase, saveGuestIssue: vi.fn(),
})

const row = (over = {}) => ({
    frequency: 'weekly', auto_send: false, target_email: 'me@example.com', target_email_verified_at: '2026-10-01T00:00:00Z',
    schedule_timezone: 'UTC', schedule_time_local: '09:00', schedule_weekday: 0, schedule_day_of_month: null, ...over,
})

const toggle = () => screen.getByRole('switch', { name: /Enable automatic delivery/ })

beforeEach(() => {
    mocks.apiFetch.mockReset().mockResolvedValue({ ok: true, json: async () => ({ deliveries: [] }) })
    mocks.config = base()
    mocks.schedule = { issue: row(), refresh: vi.fn(), save: vi.fn().mockResolvedValue({ error: null }) }
    mocks.saveIssueToSupabase.mockReset().mockResolvedValue({})
})

describe('automatic delivery needs a confirmed address', () => {
    it('can be switched on once the saved address is confirmed', () => {
        render(<ConfigureNewspaper />)
        expect(toggle()).toBeEnabled()
        expect(screen.queryByText(/Confirm your delivery email/)).not.toBeInTheDocument()
    })

    it('is locked while the address is unconfirmed, and says why', () => {
        mocks.schedule.issue = row({ target_email_verified_at: null })
        render(<ConfigureNewspaper />)
        expect(toggle()).toBeDisabled()
        expect(screen.getByText(/Confirm your delivery email above/)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Send confirmation email' })).toBeInTheDocument()
    })

    it('is locked when the typed address differs from the confirmed one', () => {
        mocks.config.targetEmail = 'new@example.com'
        render(<ConfigureNewspaper />)
        expect(toggle()).toBeDisabled()
        expect(screen.getByText(/Save this address/)).toBeInTheDocument()
    })

    it('can always be switched off', () => {
        mocks.config.autoSend = true
        mocks.schedule.issue = row({ target_email_verified_at: null, auto_send: true })
        render(<ConfigureNewspaper />)
        expect(toggle()).toBeEnabled()
    })

    it('shows why the database refused to turn it on', () => {
        mocks.config.autoSendError = 'Confirm this address before turning on automatic delivery.'
        render(<ConfigureNewspaper />)
        expect(screen.getByRole('alert')).toHaveTextContent('Confirm this address')
    })
})

describe('Send now', () => {
    beforeEach(() => { mocks.config.autoSend = true })

    it('is available once the address is confirmed', () => {
        render(<ConfigureNewspaper />)
        expect(screen.getByRole('button', { name: 'Send now' })).toBeEnabled()
    })

    it('waits for the address to be confirmed', () => {
        mocks.schedule.issue = row({ target_email_verified_at: null })
        render(<ConfigureNewspaper />)
        expect(screen.getByRole('button', { name: 'Send now' })).toBeDisabled()
    })
})

describe('schedule controls', () => {
    beforeEach(() => { mocks.config.autoSend = true })

    it('shows the pickers and the delivery history only while automatic delivery is on', () => {
        const { rerender } = render(<ConfigureNewspaper />)
        expect(screen.getByLabelText('Time')).toBeInTheDocument()
        expect(screen.getByTestId('status')).toBeInTheDocument()

        mocks.config = { ...mocks.config, autoSend: false }
        rerender(<ConfigureNewspaper />)
        expect(screen.queryByLabelText('Time')).not.toBeInTheDocument()
    })

    it('saves a frequency change to the issue as well as to the form', async () => {
        render(<ConfigureNewspaper />)
        fireEvent.click(screen.getByRole('button', { name: 'Monthly' }))
        expect(mocks.config.updateFrequency).toHaveBeenCalledWith('monthly')
        await waitFor(() => expect(mocks.schedule.save).toHaveBeenCalledWith({ frequency: 'monthly' }))
    })

    it('does not write to a database row that does not exist yet', async () => {
        mocks.config.currentIssueId = null
        render(<ConfigureNewspaper />)
        fireEvent.click(screen.getByRole('button', { name: 'Daily' }))
        expect(mocks.config.updateFrequency).toHaveBeenCalledWith('daily')
        expect(mocks.schedule.save).not.toHaveBeenCalled()
    })
})

describe('changing the delivery address', () => {
    it('re-reads the confirmation state after saving it', async () => {
        render(<ConfigureNewspaper />)
        fireEvent.blur(screen.getByPlaceholderText('e.g., you@example.com'))
        await waitFor(() => expect(mocks.schedule.refresh).toHaveBeenCalled())
    })

    it('explains why a live schedule cannot move to an unconfirmed address', async () => {
        mocks.saveIssueToSupabase.mockRejectedValue({ message: 'recipient_not_verified: confirm the recipient', code: '23514' })
        render(<ConfigureNewspaper />)
        fireEvent.blur(screen.getByPlaceholderText('e.g., you@example.com'))
        expect(await screen.findByText(/Turn off automatic delivery to change the address/)).toBeInTheDocument()
    })
})
