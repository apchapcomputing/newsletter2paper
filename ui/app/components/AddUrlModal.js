'use client'

import { useState } from 'react'
import { Modal, Box, Typography, TextField, Button, CircularProgress, Alert } from '@mui/material'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'
import { getRssFeedUrl } from '../../utils/rssUtils'
import { searchSubstack } from '../../utils/substackUtils'

export default function AddUrlModal({ open, onClose }) {
    const { addPublication } = useSelectedPublications()
    const [urlInput, setUrlInput] = useState('')
    const [isProcessing, setIsProcessing] = useState(false)
    const [error, setError] = useState(null)
    const [successCount, setSuccessCount] = useState(0)

    const handleAdd = async () => {
        setError(null)
        setSuccessCount(0)
        setIsProcessing(true)

        try {
            // Parse URLs by splitting on comma, newline, or space
            const urls = urlInput
                .split(/[\s,\n]+/)
                .map(url => url.trim())
                .filter(url => url.length > 0)

            if (urls.length === 0) {
                setError('Please enter at least one URL')
                setIsProcessing(false)
                return
            }

            let addedCount = 0

            for (const url of urls) {
                try {
                    // Validate it's a URL
                    let cleanUrl = url
                    if (!url.startsWith('http://') && !url.startsWith('https://')) {
                        cleanUrl = 'https://' + url
                    }

                    // Extract publication handle from URL (e.g., https://example.substack.com -> example)
                    const urlObj = new URL(cleanUrl)
                    const hostname = urlObj.hostname
                    const handle = hostname.replace('.substack.com', '').split('.')[0]

                    // Search for the publication to get full details
                    let publicationName = handle
                    let publisher = handle
                    let subscribers = null

                    try {
                        const searchResults = await searchSubstack(handle)
                        console.log('Search results for', handle, ':', searchResults)

                        // Find the matching publication in search results
                        // Prioritize 'user' type results as they have better author info
                        let matchingResult = searchResults.find(r =>
                            r.type === 'user' && (r.handle === handle || r.subdomain === handle)
                        )

                        // If no user result found, try publication type
                        if (!matchingResult) {
                            matchingResult = searchResults.find(r =>
                                r.type === 'publication' && (
                                    r.subdomain === handle ||
                                    (r.domain && r.domain.includes(handle))
                                )
                            )
                        }

                        // Fallback to any matching result
                        if (!matchingResult) {
                            matchingResult = searchResults.find(r =>
                                r.handle === handle ||
                                r.subdomain === handle ||
                                (r.domain && r.domain.includes(handle))
                            )
                        }

                        if (matchingResult) {
                            publicationName = matchingResult.name
                            publisher = matchingResult.publisher || handle
                            subscribers = matchingResult.subscribers
                        }
                    } catch (err) {
                        console.warn('Could not search for publication details:', err)
                    }

                    // Get RSS feed URL
                    let feedUrl
                    try {
                        feedUrl = await getRssFeedUrl(cleanUrl)
                    } catch (err) {
                        console.error('Error getting RSS feed URL:', err)
                        // Fallback to default Substack RSS feed pattern
                        feedUrl = `${cleanUrl}/feed`
                        console.log('Using default feed URL:', feedUrl)
                    }

                    // Add to selected publications (using same format as SearchModal)
                    addPublication({
                        id: handle,
                        name: publicationName,
                        title: publicationName,
                        url: cleanUrl,
                        publisher: publisher,
                        feed_url: feedUrl,
                        handle: handle,
                    })

                    // Also create/find the publication in the database
                    try {
                        const pubResponse = await fetch('/api/publications-db?action=find-or-create', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                title: publicationName,
                                url: cleanUrl,
                                rss_feed_url: feedUrl,
                                publisher: publisher
                            })
                        })

                        if (pubResponse.ok) {
                            const pubData = await pubResponse.json()
                            console.log('Publication created/found in database:', pubData.publication)
                        } else {
                            console.error('Failed to create publication in database:', await pubResponse.text())
                        }
                    } catch (dbErr) {
                        console.error('Error creating publication in database:', dbErr)
                        // Don't fail the whole operation if DB insert fails
                    }

                    addedCount++
                } catch (err) {
                    console.error(`Failed to add URL ${url}:`, err)
                    // Continue with other URLs
                }
            }

            setSuccessCount(addedCount)

            if (addedCount > 0) {
                // Clear input and close modal after a brief delay
                setTimeout(() => {
                    setUrlInput('')
                    setSuccessCount(0)
                    onClose()
                }, 1500)
            } else {
                setError('Failed to add any publications. Please check the URLs and try again.')
            }

        } catch (err) {
            console.error('Error processing URLs:', err)
            setError('An error occurred while processing the URLs')
        } finally {
            setIsProcessing(false)
        }
    }

    const handleClose = () => {
        if (!isProcessing) {
            setUrlInput('')
            setError(null)
            setSuccessCount(0)
            onClose()
        }
    }

    return (
        <Modal
            open={open}
            onClose={handleClose}
            aria-labelledby="add-url-modal-title"
        >
            <Box sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: { xs: '90%', sm: '600px' },
                maxWidth: '90vw',
                maxHeight: '90vh',
                bgcolor: '#ECECEC',
                border: '2px solid #291D18',
                boxShadow: 24,
                p: 4,
                overflow: 'auto'
            }}>
                <Typography
                    id="add-url-modal-title"
                    variant="h5"
                    component="h2"
                    sx={{
                        fontWeight: 600,
                        mb: 2,
                        color: '#291D18'
                    }}
                >
                    Add Publications via URL
                </Typography>

                <Typography variant="body2" sx={{ mb: 3, color: '#504f4e' }}>
                    Paste Substack publication URLs below. You can separate multiple URLs with commas, spaces, or new lines.
                </Typography>

                <TextField
                    fullWidth
                    multiline
                    rows={6}
                    placeholder="https://example.substack.com&#10;https://another.substack.com&#10;or separate by commas or spaces"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    disabled={isProcessing}
                    sx={{
                        mb: 2,
                        '& .MuiOutlinedInput-root': {
                            backgroundColor: '#fff',
                            '& fieldset': {
                                borderColor: '#291D18',
                                borderWidth: '2px'
                            },
                            '&:hover fieldset': {
                                borderColor: '#A44200'
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: '#A44200'
                            }
                        }
                    }}
                />

                {error && (
                    <Alert
                        severity="error"
                        sx={{
                            mb: 2,
                            backgroundColor: '#ffebee',
                            color: '#c62828',
                            border: '1px solid #c62828',
                            '& .MuiAlert-icon': {
                                color: '#c62828'
                            }
                        }}
                    >
                        {error}
                    </Alert>
                )}

                {successCount > 0 && (
                    <Alert
                        severity="success"
                        sx={{
                            mb: 2,
                            backgroundColor: '#e8f5e9',
                            color: '#2e7d32',
                            border: '1px solid #2e7d32',
                            '& .MuiAlert-icon': {
                                color: '#2e7d32'
                            }
                        }}
                    >
                        Successfully added {successCount} publication{successCount !== 1 ? 's' : ''}!
                    </Alert>
                )}

                <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                    <Button
                        variant="outlined"
                        onClick={handleClose}
                        disabled={isProcessing}
                        sx={{
                            textTransform: 'none',
                            fontWeight: 500,
                            fontSize: '1rem',
                            color: '#291D18',
                            borderColor: '#291D18',
                            borderWidth: '2px',
                            px: 3,
                            '&:hover': {
                                borderColor: '#291D18',
                                backgroundColor: 'rgba(0, 0, 0, 0.04)',
                                borderWidth: '2px'
                            }
                        }}
                    >
                        Cancel
                    </Button>
                    <Button
                        variant="contained"
                        onClick={handleAdd}
                        disabled={isProcessing || !urlInput.trim()}
                        sx={{
                            textTransform: 'none',
                            fontWeight: 500,
                            fontSize: '1rem',
                            backgroundColor: '#A44200',
                            color: '#ECECEC',
                            px: 3,
                            '&:hover': {
                                backgroundColor: '#8B3500'
                            },
                            '&:disabled': {
                                backgroundColor: '#bdbdbd',
                                color: '#fff'
                            }
                        }}
                    >
                        {isProcessing ? (
                            <>
                                <CircularProgress size={20} sx={{ mr: 1, color: '#fff' }} />
                                Processing...
                            </>
                        ) : (
                            'Add Publications'
                        )}
                    </Button>
                </Box>
            </Box>
        </Modal>
    )
}
