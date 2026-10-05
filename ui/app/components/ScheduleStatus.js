'use client'

import { useEffect, useMemo, useState } from 'react'
import { Typography } from '@mui/material'
import { createClient } from '../../lib/supabase'
import { describeSchedule } from '../../utils/scheduleStatus'

/**
 * Read-only view of the scheduler's state for one issue: when the next delivery is, whether a
 * failed one is being retried, and the last error. Reads the owner's own issue row (RLS applies).
 * `refreshKey` re-fetches, e.g. after "Send now". `fallbackNext` is shown until the scheduler has
 * set a real next_run_at (it does so within a minute of enabling automatic delivery).
 */
export default function ScheduleStatus({ issueId, refreshKey, fallbackNext }) {
    const supabase = useMemo(() => createClient(), [])
    const [issue, setIssue] = useState(null)

    useEffect(() => {
        if (!issueId) {
            setIssue(null)
            return undefined
        }
        let cancelled = false
        supabase
            .from('issues')
            .select('schedule_status, next_run_at, last_run_error')
            .eq('id', issueId)
            .maybeSingle()
            .then(({ data, error }) => {
                if (!cancelled) setIssue(error ? null : data)
            })
        return () => { cancelled = true }
    }, [issueId, refreshKey, supabase])

    const { nextAt, retryAt, error } = describeSchedule(issue)
    const next = nextAt || (retryAt ? null : fallbackNext)

    return (
        <>
            {retryAt && (
                <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'warning.main' }} role="status">
                    Delivery failed. Retrying at {retryAt.toLocaleString()}.
                </Typography>
            )}
            {next && (
                <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
                    {nextAt ? 'Next delivery' : 'First scheduled delivery'}: {next.toLocaleString()}
                </Typography>
            )}
            {error && (
                <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: 'error.main' }} role="alert">
                    {retryAt ? 'Last error' : 'Last delivery failed'}: {error}
                </Typography>
            )}
        </>
    )
}
