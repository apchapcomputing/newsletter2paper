import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const flags = { enabled: false, payload: null }
vi.mock('@/lib/analytics', () => ({
    track: vi.fn(),
    flagEnabled: vi.fn(() => flags.enabled),
    flagPayload: vi.fn(() => flags.payload),
    onFlags: vi.fn((cb) => { cb(); return () => { } }),
}))
const auth = { user: null }
vi.mock('@/contexts/useAuth', () => ({ useAuth: () => auth }))

import { track, flagEnabled } from '@/lib/analytics'
import FakeDoor, { fakeDoorFlag } from '@/app/components/FakeDoor'

describe('FakeDoor', () => {
    beforeEach(() => {
        track.mockClear()
        flagEnabled.mockClear()
        flags.enabled = false
        flags.payload = null
        auth.user = null
    })

    it('uses a dashed flag key per feature', () => {
        expect(fakeDoorFlag('send_to_ereader')).toBe('fake-door-send-to-ereader')
    })

    it('is hidden while its flag is off', () => {
        render(<FakeDoor feature="mail_printed_copy" label="Mail me a printed copy" />)
        expect(screen.queryByRole('button')).not.toBeInTheDocument()
        expect(flagEnabled).toHaveBeenCalledWith('fake-door-mail-printed-copy')
    })

    it('records the click and the early-access request', async () => {
        flags.enabled = true
        render(<FakeDoor feature="mail_printed_copy" label="Mail me a printed copy" />)
        await userEvent.click(screen.getByRole('button', { name: 'Mail me a printed copy' }))
        expect(track).toHaveBeenCalledWith('fake_door_clicked', { feature: 'mail_printed_copy', is_guest: true })
        await userEvent.click(screen.getByRole('button', { name: 'Yes, I want early access' }))
        expect(track).toHaveBeenCalledWith('early_access_requested', { feature: 'mail_printed_copy', is_guest: true })
        expect(screen.getByText(/Sign in so we can let you know/)).toBeInTheDocument()
    })

    it('thanks a signed-in user without asking for anything', async () => {
        flags.enabled = true
        auth.user = { id: 'user-1' }
        render(<FakeDoor feature="single_article" label="Add a single article" />)
        await userEvent.click(screen.getByRole('button', { name: 'Add a single article' }))
        await userEvent.click(screen.getByRole('button', { name: 'Yes, I want early access' }))
        expect(track).toHaveBeenLastCalledWith('early_access_requested', { feature: 'single_article', is_guest: false })
        expect(screen.getByText(/your account email/)).toBeInTheDocument()
    })

    it('takes its copy from the flag payload when set', () => {
        flags.enabled = true
        flags.payload = { label: 'Upgrade: $4/month' }
        render(<FakeDoor feature="upgrade_auto_send" label="Default label" />)
        expect(screen.getByRole('button', { name: 'Upgrade: $4/month' })).toBeInTheDocument()
    })
})
