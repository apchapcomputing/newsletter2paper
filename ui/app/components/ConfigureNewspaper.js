'use client'

import { useState } from 'react'
import { Box, Button, Typography, TextField, Switch, FormControlLabel } from '@mui/material'
import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'
import { useAuth } from '../../contexts/useAuth'
import { track } from '../../lib/analytics'
import FakeDoor from './FakeDoor'
import ScheduleStatus from './ScheduleStatus'
import ScheduleSettings from './ScheduleSettings'
import RecipientConfirmation from './RecipientConfirmation'
import DeliveryHistory from './DeliveryHistory'
import { useIssueSchedule } from '../../lib/useIssueSchedule'
import { isRecipientConfirmed } from '../../lib/schedule'

const FORMAT_OPTIONS = [
    { value: 'essay', label: 'Essay' },
    { value: 'newspaper', label: 'Newspaper' },
]

const FREQUENCY_OPTIONS = [
    { value: 'daily', label: 'Daily' },
    { value: 'weekly', label: 'Weekly' },
    { value: 'monthly', label: 'Monthly' },
    { value: 'custom', label: 'Custom' },
]

const ARTICLE_WINDOW_OPTIONS = [
    { value: '1', label: '1 day' },
    { value: '7', label: '7 days' },
    { value: '30', label: '30 days' },
    { value: 'custom', label: 'Custom' }
]

export default function ConfigureNewspaper() {
    const {
        newspaperTitle,
        outputMode,
        frequency,
        dateFrom,
        dateTo,
        targetEmail,
        currentIssueId,
        isAuthenticated,
        updateTitle,
        updateOutputMode,
        updateFrequency,
        updateDateFrom,
        updateDateTo,
        updateTargetEmail,
        saveIssueToSupabase,
        saveGuestIssue,
        articleWindow,
        autoSend,
        autoSendError,
        updateArticleWindow,
        updateAutoSend
    } = useNewsletterConfig()

    const { session } = useAuth()
    const [sendNowState, setSendNowState] = useState({ status: 'idle', message: '' })
    const [emailError, setEmailError] = useState(null)
    const hasRecipient = Boolean(targetEmail && targetEmail.trim())
    // The stored schedule and recipient state; re-read after Send now so history and status follow.
    const { issue, refresh, save: saveSchedule } = useIssueSchedule(currentIssueId, sendNowState.status)
    const recipientConfirmed = isRecipientConfirmed(issue, targetEmail)
    const recipientSaved = Boolean(issue?.target_email) &&
        issue.target_email.trim().toLowerCase() === (targetEmail || '').trim().toLowerCase()

    const handleSendNow = async () => {
        track('send_now_clicked')
        setSendNowState({ status: 'sending', message: '' })
        try {
            const res = await fetch(`/api/issues/${currentIssueId}/send-now`, {
                method: 'POST',
                headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {},
            })
            const data = await res.json().catch(() => ({}))
            if (!res.ok) {
                // 409: a run is already in progress; 429: sent moments ago (the message says when to retry).
                const message = res.status === 409
                    ? 'This newspaper is already being sent. Check back in a few minutes.'
                    : data.error || 'Could not start sending'
                setSendNowState({ status: 'error', message })
                return
            }
            setSendNowState({ status: 'sent', message: `Sending started. It will arrive at ${targetEmail} shortly.` })
        } catch (err) {
            setSendNowState({ status: 'error', message: 'Could not reach the server' })
        }
    }

    // Persist the email change to the DB so it's available when PDF generation fires
    const handleEmailBlur = async () => {
        setEmailError(null)
        try {
            if (isAuthenticated) {
                await saveIssueToSupabase({
                    title: newspaperTitle,
                    format: outputMode,
                    frequency,
                    remove_images: false,
                })
                refresh()
            }
        } catch (err) {
            // The value is still in context state. The one failure worth explaining is the database
            // refusing to move a live schedule to an address nobody confirmed.
            console.warn('Could not persist email to DB:', err)
            if (`${err?.message} ${err?.code}`.includes('recipient_not_verified')) {
                setEmailError('Turn off automatic delivery to change the address, then confirm the new one.')
            }
        }
    }

    const handleFrequencyChange = async (value) => {
        updateFrequency(value)
        if (currentIssueId) await saveSchedule({ frequency: value })
    }

    // Validation for custom date range
    const isCustom = frequency === 'custom'
    const dateFromMissing = isCustom && !dateFrom
    const dateToMissing = isCustom && !dateTo
    const datesReversed = isCustom && dateFrom && dateTo && dateFrom > dateTo

    const dateError = datesReversed
        ? 'Start date must be before end date'
        : (dateFromMissing || dateToMissing)
            ? 'Both dates are required for a custom range'
            : null

    return (
        <Box sx={{
            width: '100%',
            border: '2px solid black',
            p: 3,
            mb: 2
        }}>
            <Typography
                variant="h4"
                component="h2"
                sx={{
                    textAlign: 'center',
                    fontWeight: 600,
                    mb: 1,
                    fontSize: { xs: '1.5rem', sm: '2rem' }
                }}
            >
                Configure Your Newspaper
            </Typography>
            <Typography
                variant="body2"
                sx={{
                    textAlign: 'center',
                    fontStyle: 'italic',
                    color: 'text.secondary',
                    mb: 2
                }}
            >
                Configure the details for your newspaper
            </Typography>

            <Box sx={{
                width: '100%',
                height: '2px',
                backgroundColor: 'var(--black)',
                mb: 3
            }} />

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {/* Format Toggle */}
                <Box>
                    <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                        FORMAT
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        {FORMAT_OPTIONS.map(({ value, label }) => (
                            <Button
                                key={value}
                                onClick={() => updateOutputMode(value)}
                                sx={{
                                    flex: 1,
                                    py: 1.5,
                                    fontWeight: 'medium',
                                    textTransform: 'none',
                                    fontSize: '1rem',
                                    backgroundColor: '#f5f5f5',
                                    color: outputMode === value ? 'var(--primary-light)' : 'var(--black)',
                                    border: '1px solid',
                                    borderColor: outputMode === value ? 'var(--primary-dark)' : '#ccc',
                                    '&:hover': {
                                        backgroundColor: '#f5f5f5',
                                        borderColor: 'var(--black)',
                                    },
                                }}
                            >
                                {label}
                            </Button>
                        ))}
                    </Box>
                </Box>

                {/* Title Input */}
                <Box>
                    <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                        TITLE
                    </Typography>
                    <TextField
                        variant="outlined"
                        fullWidth
                        value={newspaperTitle}
                        onChange={(e) => updateTitle(e.target.value)}
                        placeholder="e.g., Morning News, Weekly Digest"
                        sx={{ '& .MuiOutlinedInput-root': { backgroundColor: '#f5f5f5' } }}
                    />
                </Box>

                {/* Article Window */}
                <Box>
                    <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                        ARTICLE WINDOW
                    </Typography>
                    <Typography
                        variant="body2"
                        sx={{ fontStyle: 'italic', color: 'text.secondary', mb: 2 }}
                    >
                        Choose the time period to retrieve articles from
                    </Typography>

                    {/* Article window toggle buttons */}
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {ARTICLE_WINDOW_OPTIONS.map(({ value, label }) => (
                            <Button
                                key={value}
                                onClick={() => updateArticleWindow(value)}
                                sx={{
                                    flex: 1,
                                    py: 1.5,
                                    fontWeight: 'medium',
                                    textTransform: 'none',
                                    fontSize: '1rem',
                                    backgroundColor: '#f5f5f5',
                                    color: articleWindow === value ? 'var(--primary-light)' : 'var(--black)',
                                    border: '1px solid',
                                    borderColor: articleWindow === value ? 'var(--primary-dark)' : '#ccc',
                                    '&:hover': {
                                        backgroundColor: '#f5f5f5',
                                        borderColor: 'var(--black)',
                                    },
                                }}
                            >
                                {label}
                            </Button>
                        ))}
                    </Box>

                    {/* Custom date range inputs for ARTICLE_WINDOW when 'custom' */}
                    {articleWindow === 'custom' && (
                        <div className="mt-4">
                            <div className="flex flex-col sm:flex-row gap-4">
                                <div className="flex-1">
                                    <label htmlFor="date-from" className="block text-sm font-medium text-gray-700 mb-1">
                                        From
                                    </label>
                                    <input
                                        id="date-from"
                                        type="date"
                                        value={dateFrom}
                                        max={dateTo || undefined}
                                        onChange={(e) => updateDateFrom(e.target.value)}
                                        className={[
                                            'w-full px-3 py-2 border-1 bg-[#f5f5f5] text-sm focus:outline-none focus:border-black',
                                            (dateFromMissing || datesReversed) ? 'border-error' : 'border-black'
                                        ].join(' ')}
                                    />
                                </div>
                                <div className="flex-1">
                                    <label htmlFor="date-to" className="block text-sm font-medium text-gray-700 mb-1">
                                        To
                                    </label>
                                    <input
                                        id="date-to"
                                        type="date"
                                        value={dateTo}
                                        min={dateFrom || undefined}
                                        onChange={(e) => updateDateTo(e.target.value)}
                                        className={[
                                            'w-full px-3 py-2 border-1 bg-[#f5f5f5] text-sm focus:outline-none focus:border-black',
                                            (dateToMissing || datesReversed) ? 'border-error' : 'border-black'
                                        ].join(' ')}
                                    />
                                </div>
                            </div>

                            {/* Validation error message */}
                            {dateError && (
                                <p className="mt-2 text-sm text-error-light font-medium" role="alert">
                                    {dateError}
                                </p>
                            )}
                        </div>
                    )}
                </Box>

                {/* Auto-send toggle (authenticated users only) */}
                {isAuthenticated && (
                    <Box>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={autoSend}
                                    onChange={(e) => updateAutoSend(e.target.checked)}
                                    // Automatic delivery needs a confirmed recipient; turning it off is always allowed.
                                    disabled={!autoSend && (!hasRecipient || !recipientConfirmed)}
                                    color="primary"
                                />
                            }
                            label="Enable automatic delivery"
                        />
                        {!autoSend && !hasRecipient && (
                            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                Add a delivery email below to enable automatic delivery.
                            </Typography>
                        )}
                        {!autoSend && hasRecipient && !recipientConfirmed && (
                            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                Confirm your delivery email below to enable automatic delivery.
                            </Typography>
                        )}
                        {autoSendError && (
                            <Typography variant="body2" role="alert" sx={{ color: 'error.main' }}>
                                {autoSendError}
                            </Typography>
                        )}
                        <FakeDoor
                            feature="upgrade_auto_send"
                            label="Automatic delivery will be a paid feature. Reserve founder pricing"
                            description="Automatic delivery is free while we're in beta and will become part of a paid plan. Want founder pricing when it launches?"
                            sx={{ px: 0 }}
                        />
                    </Box>
                )}

                {/* Send Schedule shown when authenticated and autoSend enabled */}
                {isAuthenticated && autoSend && (
                    <Box>
                        <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                            SEND SCHEDULE
                        </Typography>
                        <Typography
                            variant="body2"
                            sx={{ fontStyle: 'italic', color: 'text.secondary', mb: 2 }}
                        >
                            Choose how often to automatically send the PDF
                        </Typography>

                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                            {FREQUENCY_OPTIONS.filter(opt => opt.value !== 'custom').map(({ value, label }) => (
                                <Button
                                    key={value}
                                    onClick={() => handleFrequencyChange(value)}
                                    sx={{
                                        flex: 1,
                                        py: 1.5,
                                        fontWeight: 'medium',
                                        textTransform: 'none',
                                        fontSize: '1rem',
                                        backgroundColor: '#f5f5f5',
                                        color: frequency === value ? 'var(--primary-light)' : 'var(--black)',
                                        border: '1px solid',
                                        borderColor: frequency === value ? 'var(--primary-dark)' : '#ccc',
                                        '&:hover': {
                                            backgroundColor: '#f5f5f5',
                                            borderColor: 'var(--black)',
                                        },
                                    }}
                                >
                                    {label}
                                </Button>
                            ))}
                        </Box>

                        <ScheduleSettings frequency={frequency} issue={issue} onSave={saveSchedule} />

                        <ScheduleStatus
                            issueId={currentIssueId}
                            refreshKey={`${sendNowState.status}:${issue?.frequency}:${issue?.schedule_weekday}:${issue?.schedule_day_of_month}:${issue?.schedule_time_local}:${issue?.schedule_timezone}`}
                        />

                        <Button
                            variant="outlined"
                            onClick={handleSendNow}
                            disabled={!currentIssueId || !targetEmail || !recipientConfirmed || sendNowState.status === 'sending'}
                            sx={{ mt: 1.5, textTransform: 'none' }}
                        >
                            {sendNowState.status === 'sending' ? 'Sending…' : 'Send now'}
                        </Button>
                        {sendNowState.message && (
                            <Typography
                                variant="caption"
                                role={sendNowState.status === 'error' ? 'alert' : 'status'}
                                sx={{ display: 'block', mt: 0.5, color: sendNowState.status === 'error' ? 'error.main' : 'text.secondary' }}
                            >
                                {sendNowState.message}
                            </Typography>
                        )}

                        <DeliveryHistory issueId={currentIssueId} refreshKey={sendNowState.status} />
                    </Box>
                )}

                {/* Email delivery (only when authenticated). Shown before automatic delivery is enabled, since enabling it needs an address. */}
                {isAuthenticated && (
                    <Box>
                        <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                            EMAIL DELIVERY
                        </Typography>
                        <Typography
                            variant="body2"
                            sx={{ fontStyle: 'italic', color: 'text.secondary', mb: 2 }}
                        >
                            Send the PDF to this address after generation (optional)
                        </Typography>
                        <TextField
                            variant="outlined"
                            fullWidth
                            type="email"
                            value={targetEmail}
                            onChange={(e) => updateTargetEmail(e.target.value)}
                            onBlur={handleEmailBlur}
                            placeholder="e.g., you@example.com"
                            helperText={
                                emailError || (!hasRecipient ? 'Enter an email to enable automatic delivery' : '')
                            }
                            error={Boolean(emailError)}
                            sx={{
                                '& .MuiOutlinedInput-root': {
                                    backgroundColor: autoSend ? '#ffffff' : '#efefef'
                                }
                            }}
                        />
                        <RecipientConfirmation
                            issueId={currentIssueId}
                            email={(targetEmail || '').trim()}
                            saved={recipientSaved}
                            confirmed={recipientConfirmed}
                            onRequested={refresh}
                        />
                    </Box>
                )}
            </Box>
        </Box>
    )
}