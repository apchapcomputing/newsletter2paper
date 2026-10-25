'use client'

import { useEffect, useId, useState } from 'react'
import { Box, Typography } from '@mui/material'
import { apiFetch } from '../../lib/apiFetch'
import { friendlyError } from '../../utils/scheduleStatus'

const STATUS_LABELS = {
    sent: 'Delivered',
    skipped: 'Skipped (no new articles)',
    sending: 'Sending',
    pending: 'Waiting',
    failed: 'Failed, will retry',
    abandoned: 'Not delivered',
}

/** One line per edition: what happened, when, and why not if it failed. */
export function describeDelivery(delivery) {
    const at = delivery.sent_at || delivery.scheduled_for || delivery.created_at
    const date = at ? new Date(at) : null
    const parts = [STATUS_LABELS[delivery.status] || delivery.status]
    if (delivery.status === 'sent' && delivery.articles_count != null) {
        parts.push(`${delivery.articles_count} ${delivery.articles_count === 1 ? 'article' : 'articles'}`)
    }
    if (delivery.status === 'sent' && delivery.opened_at) parts.push('opened')
    return {
        id: delivery.id,
        when: date && !Number.isNaN(date.getTime()) ? date.toLocaleString() : '',
        kind: delivery.trigger === 'manual' ? 'Sent manually' : 'Scheduled',
        summary: parts.join(' · '),
        error: delivery.status === 'sent' || delivery.status === 'skipped' ? null : friendlyError(delivery.error),
    }
}

export default function DeliveryHistory({ issueId, refreshKey }) {
    const [state, setState] = useState({ status: 'idle', deliveries: [] })
    const [open, setOpen] = useState(false)
    const listId = useId()

    useEffect(() => {
        if (!issueId) {
            setState({ status: 'idle', deliveries: [] })
            return undefined
        }
        let cancelled = false
        apiFetch(`/api/issues/${issueId}/deliveries?limit=10`)
            .then(async (res) => {
                const data = await res.json().catch(() => ({}))
                if (cancelled) return
                setState(res.ok
                    ? { status: 'ready', deliveries: data.deliveries || [] }
                    : { status: 'error', deliveries: [] })
            })
            .catch(() => { if (!cancelled) setState({ status: 'error', deliveries: [] }) })
        return () => { cancelled = true }
    }, [issueId, refreshKey])

    if (state.status === 'error') {
        return (
            <Typography variant="caption" sx={{ display: 'block', mt: 2, color: 'text.secondary' }}>
                Delivery history is unavailable right now.
            </Typography>
        )
    }
    if (state.deliveries.length === 0) return null

    return (
        <Box component="section" aria-label="Delivery history" sx={{ mt: 2 }}>
            <button
                type="button"
                className="n2p-link"
                aria-expanded={open}
                aria-controls={listId}
                onClick={() => setOpen((o) => !o)}
            >
                {open ? 'Hide' : 'Show'} recent deliveries ({state.deliveries.length})
            </button>
            <Box component="ul" id={listId} hidden={!open} sx={{ listStyle: 'none', p: 0, m: 0, display: open ? 'block' : 'none' }}>
                {state.deliveries.map((delivery) => {
                    const line = describeDelivery(delivery)
                    return (
                        <Box component="li" key={line.id} sx={{ py: 0.5, borderTop: '2px solid var(--paper-sunk)' }}>
                            <Typography variant="caption" sx={{ display: 'block' }}>
                                {line.when} · {line.kind}
                            </Typography>
                            <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                                {line.summary}
                            </Typography>
                            {line.error && (
                                <Typography variant="caption" sx={{ display: 'block', color: 'error.main' }}>
                                    {line.error}
                                </Typography>
                            )}
                        </Box>
                    )
                })}
            </Box>
        </Box>
    )
}
