'use client'

import { useState } from 'react'
import { Button, Typography } from '@mui/material'
import { apiFetch } from '../../lib/apiFetch'
import { track } from '../../lib/analytics'

/**
 * Shown under the delivery address while it is unconfirmed. Scheduled emails only go to an address
 * that confirmed a link (the account's own address counts as confirmed), so this explains why
 * automatic delivery is locked and lets the owner request the link. The page re-reads the issue
 * when the tab regains focus, so confirming in another tab unlocks it without a reload.
 */
export default function RecipientConfirmation({ issueId, email, saved, confirmed, onRequested }) {
    const [state, setState] = useState({ status: 'idle', message: '' })

    if (!email || confirmed) return null

    const request = async () => {
        setState({ status: 'sending', message: '' })
        try {
            const res = await apiFetch(`/api/issues/${issueId}/target-email/verify`, { method: 'POST' })
            const data = await res.json().catch(() => ({}))
            if (!res.ok) {
                setState({ status: 'error', message: data.error || 'Could not send the confirmation email' })
                return
            }
            if (data.verified) {
                setState({ status: 'idle', message: '' })
                onRequested?.()
                return
            }
            track('recipient_verification_requested')
            setState({ status: 'sent', message: `We sent a confirmation link to ${email}. Open it, press Confirm, then come back here.` })
            onRequested?.()
        } catch {
            setState({ status: 'error', message: 'Could not reach the server' })
        }
    }

    return (
        <div>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 1 }}>
                {saved
                    ? 'Automatic delivery to this address needs a one-time confirmation.'
                    : 'Save this address (click outside the field) to confirm it for automatic delivery.'}
            </Typography>
            {saved && (
                <Button
                    size="small"
                    variant="outlined"
                    onClick={request}
                    disabled={state.status === 'sending'}
                    sx={{ mt: 1, textTransform: 'none' }}
                >
                    {state.status === 'sending' ? 'Sending…' : state.status === 'sent' ? 'Send again' : 'Send confirmation email'}
                </Button>
            )}
            {state.message && (
                <Typography
                    variant="caption"
                    role={state.status === 'error' ? 'alert' : 'status'}
                    sx={{ display: 'block', mt: 0.5, color: state.status === 'error' ? 'error.main' : 'text.secondary' }}
                >
                    {state.message}
                </Typography>
            )}
        </div>
    )
}
