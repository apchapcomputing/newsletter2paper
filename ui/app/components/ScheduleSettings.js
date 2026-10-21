'use client'

import { useState } from 'react'
import { MenuItem, TextField, Typography, Box } from '@mui/material'
import { WEEKDAYS, describeCadence, timezoneOptions } from '../../lib/schedule'

const DAYS_OF_MONTH = Array.from({ length: 31 }, (_, i) => i + 1)

/**
 * When automatic delivery runs: weekday or day of month (by frequency), local time and timezone.
 * Saves each change straight to the issue; changing the schedule restarts the countdown to the
 * next delivery, which the note below says so the reset is not a surprise.
 */
export default function ScheduleSettings({ frequency, issue, onSave }) {
    const [error, setError] = useState(null)
    if (!issue) return null

    const timezone = issue.schedule_timezone || 'UTC'
    const time = (issue.schedule_time_local || '09:00').slice(0, 5)

    const change = async (fields) => {
        setError(null)
        const { error: saveError } = await onSave(fields)
        if (saveError) setError("Couldn't save the schedule. Try again.")
    }

    return (
        <Box sx={{ mt: 2 }}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                {frequency === 'weekly' && (
                    <TextField
                        select
                        label="Day"
                        size="small"
                        value={issue.schedule_weekday ?? ''}
                        onChange={(e) => change({ schedule_weekday: Number(e.target.value) })}
                        sx={{ minWidth: 150, '& .MuiOutlinedInput-root': { backgroundColor: '#f5f5f5' } }}
                    >
                        {issue.schedule_weekday == null && <MenuItem value="" disabled>Choose a day</MenuItem>}
                        {WEEKDAYS.map((name, index) => (
                            <MenuItem key={name} value={index}>{name}</MenuItem>
                        ))}
                    </TextField>
                )}
                {frequency === 'monthly' && (
                    <TextField
                        select
                        label="Day of month"
                        size="small"
                        value={issue.schedule_day_of_month ?? ''}
                        onChange={(e) => change({ schedule_day_of_month: Number(e.target.value) })}
                        sx={{ minWidth: 150, '& .MuiOutlinedInput-root': { backgroundColor: '#f5f5f5' } }}
                    >
                        {issue.schedule_day_of_month == null && <MenuItem value="" disabled>Choose a day</MenuItem>}
                        {DAYS_OF_MONTH.map((day) => (
                            <MenuItem key={day} value={day}>{day}</MenuItem>
                        ))}
                    </TextField>
                )}
                <TextField
                    label="Time"
                    type="time"
                    size="small"
                    value={time}
                    onChange={(e) => e.target.value && change({ schedule_time_local: e.target.value })}
                    slotProps={{ inputLabel: { shrink: true } }}
                    sx={{ minWidth: 130, '& .MuiOutlinedInput-root': { backgroundColor: '#f5f5f5' } }}
                />
                <TextField
                    select
                    label="Timezone"
                    size="small"
                    value={timezone}
                    onChange={(e) => change({ schedule_timezone: e.target.value })}
                    sx={{ minWidth: 220, '& .MuiOutlinedInput-root': { backgroundColor: '#f5f5f5' } }}
                >
                    {timezoneOptions(timezone).map((zone) => (
                        <MenuItem key={zone} value={zone}>{zone}</MenuItem>
                    ))}
                </TextField>
            </Box>
            <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
                {describeCadence({ ...issue, frequency })}
                {frequency === 'monthly' && issue.schedule_day_of_month > 28 ? '. Shorter months send on their last day.' : ''}
            </Typography>
            <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                Changing the schedule restarts the countdown to your next delivery.
            </Typography>
            {error && (
                <Typography variant="caption" role="alert" sx={{ display: 'block', color: 'error.main' }}>{error}</Typography>
            )}
        </Box>
    )
}
