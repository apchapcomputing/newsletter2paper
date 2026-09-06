'use client'

import { Box, Button, Typography, TextField, Switch, FormControlLabel } from '@mui/material'
import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'
import { useAuth } from '../../contexts/useAuth'

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
        updateArticleWindow,
        updateAutoSend
    } = useNewsletterConfig()

    // Persist the email change to the DB so it's available when PDF generation fires
    const handleEmailBlur = async () => {
        try {
            if (isAuthenticated) {
                await saveIssueToSupabase({
                    title: newspaperTitle,
                    format: outputMode,
                    frequency,
                    remove_images: false,
                })
            }
        } catch (err) {
            // Non-critical – silently ignore, the value is still in context state
            console.warn('Could not persist email to DB:', err)
        }
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

    // Compute a next scheduled Date for display based on frequency selection
    const computeNextScheduled = (freq) => {
        const now = new Date()
        const d = new Date(now)
        if (!freq) return d

        switch (freq) {
            case 'daily':
                d.setDate(d.getDate() + 1)
                break
            case 'weekly':
                d.setDate(d.getDate() + 7)
                break
            case 'monthly':
                d.setMonth(d.getMonth() + 1)
                break
            default:
                // Fallback to one week
                d.setDate(d.getDate() + 7)
        }

        return d
    }

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
                                    color="primary"
                                />
                            }
                            label="Enable automatic delivery"
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
                                    onClick={() => updateFrequency(value)}
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

                        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
                            Next scheduled: {computeNextScheduled(frequency).toLocaleString()}
                        </Typography>
                    </Box>
                )}

                {/* Email delivery (only when authenticated). When automatic delivery is OFF show field disabled/greyed so users know automation isn't used. */}
                {isAuthenticated && autoSend && (
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
                                !targetEmail ? 'Enter an email to enable automatic delivery' : ''
                            }
                            sx={{
                                '& .MuiOutlinedInput-root': {
                                    backgroundColor: autoSend ? '#ffffff' : '#efefef'
                                }
                            }}
                        />
                    </Box>
                )}
            </Box>
        </Box>
    )
}