'use client'

import { useEffect, useMemo, useState } from 'react'
import { Typography } from '@mui/material'
import { createClient } from '../../lib/supabase'
import { describeSchedule } from '../../utils/scheduleStatus'

/**
 * Read-only view of the scheduler's state for one issue: when the next delivery is, whether a
 * failed one is being retried, and the last error. Reads the owner's own issue row (RLS applies).
 * `refreshKey` re-fetches, e.g. after "Send now" or a schedule change. Right after enabling or
 * changing the schedule the scheduler has not yet picked the next slot (it does within a minute),
 * so there is no date to show until then; nothing is guessed on the client.
 */
export default function ScheduleStatus({ issueId, refreshKey }) {
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
    const scheduling = Boolean(issue) && !nextAt && !retryAt

    return (
        <>
            {retryAt && (
                <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'warning.main' }} role="status">
                    Delivery failed. Retrying at {retryAt.toLocaleString()}.
                </Typography>
            )}
            {nextAt && (
                <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
                    Next delivery: {nextAt.toLocaleString()}
                </Typography>
            )}
            {scheduling && (
                <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }} role="status">
                    Working out your next delivery…
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
