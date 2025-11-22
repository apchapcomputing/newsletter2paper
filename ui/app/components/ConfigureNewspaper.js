'use client'

import { Box, Typography, TextField, Select, MenuItem, FormControl } from '@mui/material'
import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'

export default function ConfigureNewspaper() {
    const { newspaperTitle, outputMode, updateTitle, updateOutputMode } = useNewsletterConfig()

    const handleNewspaperTitleChange = (event) => {
        updateTitle(event.target.value)
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
                {/* Title Input */}
                <Box>
                    <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                        TITLE
                    </Typography>
                    <TextField
                        variant="outlined"
                        fullWidth
                        value={newspaperTitle}
                        onChange={handleNewspaperTitleChange}
                        placeholder="e.g., Morning News, Weekly Digest"
                        sx={{
                            '& .MuiOutlinedInput-root': {
                                backgroundColor: '#f5f5f5'
                            }
                        }}
                    />
                </Box>

                {/* Printing Schedule and Format Row */}
                <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', sm: 'row' } }}>
                    {/* Printing Schedule */}
                    <Box sx={{ flex: 1 }}>
                        <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                            PRINTING SCHEDULE
                        </Typography>
                        <FormControl fullWidth>
                            <Select
                                value="weekly"
                                disabled
                                displayEmpty
                                sx={{
                                    backgroundColor: '#f5f5f5'
                                }}
                            >
                                <MenuItem value="" disabled>
                                    Select frequency
                                </MenuItem>
                                <MenuItem value="daily">Last 24 Hours</MenuItem>
                                <MenuItem value="weekly">Last Week</MenuItem>
                                <MenuItem value="monthly">Last Month</MenuItem>
                            </Select>
                        </FormControl>
                    </Box>

                    {/* Format */}
                    <Box sx={{ flex: 1 }}>
                        <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                            FORMAT
                        </Typography>
                        <FormControl fullWidth>
                            <Select
                                value={outputMode}
                                disabled
                                onChange={(e) => updateOutputMode(e.target.value)}
                                sx={{
                                    backgroundColor: '#f5f5f5'
                                }}
                            >
                                <MenuItem value="" disabled>
                                    Select format
                                </MenuItem>
                                <MenuItem value="newspaper">Newspaper</MenuItem>
                                <MenuItem value="essay">Essay</MenuItem>
                            </Select>
                        </FormControl>
                    </Box>
                </Box>
            </Box>
        </Box>
    )
}