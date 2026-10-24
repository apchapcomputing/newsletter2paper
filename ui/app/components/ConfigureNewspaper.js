'use client'

import { useState } from 'react'
import { Switch, FormControlLabel } from '@mui/material'
import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'
import { useAuth } from '../../contexts/useAuth'
import { track } from '../../lib/analytics'
import FakeDoor from './FakeDoor'
import OptionButtons from './OptionButtons'
import ScheduleStatus from './ScheduleStatus'
import ScheduleSettings from './ScheduleSettings'
import RecipientConfirmation from './RecipientConfirmation'
import DeliveryHistory from './DeliveryHistory'
import { useIssueSchedule } from '../../lib/useIssueSchedule'
import { isRecipientConfirmed } from '../../lib/schedule'
import { articleWindowError } from '../../lib/createFlow'

const FORMAT_OPTIONS = [
    { value: 'newspaper', label: 'Newspaper' },
    { value: 'essay', label: 'Essay' },
]

const FREQUENCY_OPTIONS = [
    { value: 'daily', label: 'Daily' },
    { value: 'weekly', label: 'Weekly' },
    { value: 'monthly', label: 'Monthly' },
]

const ARTICLE_WINDOW_OPTIONS = [
    { value: '1', label: 'Last day' },
    { value: '7', label: 'Last week' },
    { value: '30', label: 'Last month' },
    { value: 'custom', label: 'Custom' }
]

// Step 2: format, title and article window for everyone; delivery (address, schedule, send now)
// for signed-in users.
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
    const dateError = articleWindowError({ articleWindow, dateFrom, dateTo })
    const datesReversed = articleWindow === 'custom' && dateFrom && dateTo && dateFrom > dateTo

    return (
        <>
            <div className="n2p-field">
                <span className="n2p-label" id="format-label">Format</span>
                <div style={{ marginTop: 'var(--space-2)' }}>
                    <OptionButtons labelId="format-label" options={FORMAT_OPTIONS} value={outputMode} onChange={updateOutputMode} />
                </div>
            </div>

            <div className="n2p-field">
                <label className="n2p-label" htmlFor="paper-title">Title</label>
                <input
                    id="paper-title"
                    className="n2p-input"
                    type="text"
                    value={newspaperTitle}
                    onChange={(e) => updateTitle(e.target.value)}
                    placeholder="e.g., Morning News, Weekly Digest"
                    maxLength={40}
                    autoComplete="off"
                    style={{ marginTop: 'var(--space-2)' }}
                />
            </div>

            <div className="n2p-field" style={{ marginBottom: 0 }}>
                <span className="n2p-label" id="window-label">Article window</span>
                <p className="n2p-help">Choose the time period to retrieve articles from</p>
                <OptionButtons labelId="window-label" options={ARTICLE_WINDOW_OPTIONS} value={articleWindow} onChange={updateArticleWindow} />

                {/* Custom date range inputs for the article window */}
                {articleWindow === 'custom' && (
                    <>
                        <div className="n2p-dates">
                            <div className="n2p-field">
                                <label className="n2p-label" htmlFor="date-from">From</label>
                                <input
                                    id="date-from"
                                    className="n2p-input"
                                    type="date"
                                    value={dateFrom}
                                    max={dateTo || undefined}
                                    onChange={(e) => updateDateFrom(e.target.value)}
                                    aria-invalid={(!dateFrom || datesReversed) ? 'true' : undefined}
                                    aria-describedby={dateError ? 'date-error' : undefined}
                                    style={{ marginTop: 'var(--space-2)' }}
                                />
                            </div>
                            <div className="n2p-field">
                                <label className="n2p-label" htmlFor="date-to">To</label>
                                <input
                                    id="date-to"
                                    className="n2p-input"
                                    type="date"
                                    value={dateTo}
                                    min={dateFrom || undefined}
                                    onChange={(e) => updateDateTo(e.target.value)}
                                    aria-invalid={(!dateTo || datesReversed) ? 'true' : undefined}
                                    aria-describedby={dateError ? 'date-error' : undefined}
                                    style={{ marginTop: 'var(--space-2)' }}
                                />
                            </div>
                        </div>
                        {dateError && (
                            <p className="n2p-error" id="date-error" role="alert">{dateError}</p>
                        )}
                    </>
                )}
            </div>

            {isAuthenticated && (
                <section className="n2p-section" aria-labelledby="delivery-title">
                    <h3 className="n2p-section__title" id="delivery-title">Email delivery</h3>

                    {/* Email delivery. Shown before automatic delivery is enabled, since enabling it needs an address. */}
                    <div className="n2p-field">
                        <label className="n2p-label" htmlFor="target-email">Send the PDF to</label>
                        <p className="n2p-help">Send the PDF to this address after generation (optional)</p>
                        <input
                            id="target-email"
                            className="n2p-input"
                            type="email"
                            value={targetEmail}
                            onChange={(e) => updateTargetEmail(e.target.value)}
                            onBlur={handleEmailBlur}
                            placeholder="e.g., you@example.com"
                            aria-invalid={emailError ? 'true' : undefined}
                            aria-describedby="target-email-note"
                        />
                        <div id="target-email-note">
                            {emailError
                                ? <p className="n2p-error">{emailError}</p>
                                : !hasRecipient && <p className="n2p-help">Enter an email to enable automatic delivery</p>}
                        </div>
                        <RecipientConfirmation
                            issueId={currentIssueId}
                            email={(targetEmail || '').trim()}
                            saved={recipientSaved}
                            confirmed={recipientConfirmed}
                            onRequested={refresh}
                        />
                    </div>

                    {/* Auto-send toggle (authenticated users only) */}
                    <div className="n2p-field">
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
                            <p className="n2p-help">Add a delivery email above to enable automatic delivery.</p>
                        )}
                        {!autoSend && hasRecipient && !recipientConfirmed && (
                            <p className="n2p-help">Confirm your delivery email above to enable automatic delivery.</p>
                        )}
                        {autoSendError && (
                            <p className="n2p-error" role="alert">{autoSendError}</p>
                        )}
                        <FakeDoor
                            feature="upgrade_auto_send"
                            label="Automatic delivery will be a paid feature. Reserve founder pricing"
                            description="Automatic delivery is free while we're in beta and will become part of a paid plan. Want founder pricing when it launches?"
                            sx={{ px: 0 }}
                        />
                    </div>

                    {/* Send Schedule shown when authenticated and autoSend enabled */}
                    {autoSend && (
                        <div className="n2p-field" style={{ marginBottom: 0 }}>
                            <span className="n2p-label" id="schedule-label">Send schedule</span>
                            <p className="n2p-help">Choose how often to automatically send the PDF</p>

                            <OptionButtons labelId="schedule-label" options={FREQUENCY_OPTIONS} value={frequency} onChange={handleFrequencyChange} />

                            <ScheduleSettings frequency={frequency} issue={issue} onSave={saveSchedule} />

                            <ScheduleStatus
                                issueId={currentIssueId}
                                refreshKey={`${sendNowState.status}:${issue?.frequency}:${issue?.schedule_weekday}:${issue?.schedule_day_of_month}:${issue?.schedule_time_local}:${issue?.schedule_timezone}`}
                            />

                            <button
                                type="button"
                                className="n2p-btn"
                                style={{ marginTop: 'var(--space-3)' }}
                                onClick={handleSendNow}
                                disabled={!currentIssueId || !targetEmail || !recipientConfirmed || sendNowState.status === 'sending'}
                            >
                                {sendNowState.status === 'sending' ? 'Sending…' : 'Send now'}
                            </button>
                            {sendNowState.message && (
                                <p
                                    className={sendNowState.status === 'error' ? 'n2p-error' : 'n2p-help'}
                                    role={sendNowState.status === 'error' ? 'alert' : 'status'}
                                >
                                    {sendNowState.message}
                                </p>
                            )}

                            <DeliveryHistory issueId={currentIssueId} refreshKey={sendNowState.status} />
                        </div>
                    )}
                </section>
            )}
        </>
    )
}
