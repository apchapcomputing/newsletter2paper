'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { createClient } from './supabase'

const COLUMNS = 'frequency, auto_send, target_email, target_email_verified_at, schedule_timezone, schedule_time_local, schedule_weekday, schedule_day_of_month'

/**
 * The owner's view of one issue's schedule and recipient, read from the issue row (RLS applies)
 * and written back directly. Scheduler-owned columns (next_run_at, ...) are not writable from
 * the browser; ScheduleStatus reads those.
 *
 * `save(fields)` updates the row and resolves to `{ error }`; a change to the cadence restarts the
 * countdown to the next delivery (a database trigger clears next_run_at).
 */
export function useIssueSchedule(issueId, refreshKey) {
    const supabase = useMemo(() => createClient(), [])
    const [issue, setIssue] = useState(null)
    const [version, setVersion] = useState(0)

    useEffect(() => {
        if (!issueId) {
            setIssue(null)
            return undefined
        }
        let cancelled = false
        supabase.from('issues').select(COLUMNS).eq('id', issueId).maybeSingle()
            .then(({ data, error }) => {
                if (!cancelled) setIssue(error ? null : data)
            })
        return () => { cancelled = true }
    }, [issueId, refreshKey, version, supabase])

    // The confirmation happens in another tab (the email link); re-read when the owner comes back.
    useEffect(() => {
        const onFocus = () => setVersion((v) => v + 1)
        window.addEventListener('focus', onFocus)
        return () => window.removeEventListener('focus', onFocus)
    }, [])

    const refresh = useCallback(() => setVersion((v) => v + 1), [])

    const save = useCallback(async (fields) => {
        if (!issueId) return { error: null }
        const { error } = await supabase.from('issues').update(fields).eq('id', issueId)
        if (!error) setIssue((current) => (current ? { ...current, ...fields } : current))
        return { error }
    }, [issueId, supabase])

    return { issue, refresh, save }
}
