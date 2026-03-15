'use client'

import { Box, Button, Typography, TextField } from '@mui/material'
import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'

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

export default function ConfigureNewspaper() {
    const {
        newspaperTitle,
        outputMode,
        frequency,
        dateFrom,
        dateTo,
        updateTitle,
        updateOutputMode,
        updateFrequency,
        updateDateFrom,
        updateDateTo,
    } = useNewsletterConfig()

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

                {/* Printing Schedule */}
                <Box>
                    <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                        PRINTING SCHEDULE
                    </Typography>
                    <Typography
                        variant="body2"
                        sx={{ fontStyle: 'italic', color: 'text.secondary', mb: 2 }}
                    >
                        Choose the time period to retrieve articles from
                    </Typography>

                    {/* Frequency toggle buttons */}
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {FREQUENCY_OPTIONS.map(({ value, label }) => (
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

                    {/* Custom date range inputs */}
                    {isCustom && (
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
            </Box>
        </Box>
    )
}