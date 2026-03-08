'use client'

import { useState } from 'react'
import { Modal, Box, Typography, TextField, Button, CircularProgress, Alert } from '@mui/material'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'
import { getRssFeedUrl } from '../../utils/rssUtils'
import { searchSubstack } from '../../utils/substackUtils'
import logger from '../../utils/logger'

export default function AddUrlModal({ open, onClose, onPublicationAdded }) {
    const { addPublication, updatePublicationId } = useSelectedPublications()
    const [urlInput, setUrlInput] = useState('')
    const [isProcessing, setIsProcessing] = useState(false)
    const [error, setError] = useState(null)
    const [successCount, setSuccessCount] = useState(0)
    const [failedUrls, setFailedUrls] = useState([])

    const handleAdd = async () => {
        setError(null)
        setSuccessCount(0)
        setFailedUrls([])
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

            logger.log(`Processing ${urls.length} URL(s):`, urls)

            let addedCount = 0
            const failed = []

            for (const url of urls) {
                try {
                    logger.log(`Processing URL: ${url}`)

                    // Validate it's a URL
                    let cleanUrl = url
                    if (!url.startsWith('http://') && !url.startsWith('https://')) {
                        cleanUrl = 'https://' + url
                    }

                    // Validate URL format
                    let urlObj
                    try {
                        urlObj = new URL(cleanUrl)
                    } catch (urlError) {
                        throw new Error(`Invalid URL format: ${url}`)
                    }

                    // Extract publication handle from URL (e.g., https://example.substack.com -> example)
                    const hostname = urlObj.hostname

                    // Validate it looks like a Substack URL
                    if (!hostname.includes('substack.com') && !hostname.includes('.')) {
                        logger.warn(`URL may not be a valid Substack publication: ${hostname}`)
                    }

                    const handle = hostname.replace('.substack.com', '').split('.')[0]

                    // Search for the publication to get full details
                    let publicationName = handle
                    let publisher = handle
                    let subscribers = null

                    try {
                        const searchResults = await searchSubstack(handle)
                        logger.log('Search results for', handle, ':', searchResults)

                        if (!searchResults || searchResults.length === 0) {
                            logger.warn(`No Substack search results found for handle: ${handle}`)
                        }

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
                        logger.warn('Could not search for publication details:', err)
                    }

                    // Get RSS feed URL
                    let feedUrl
                    try {
                        feedUrl = await getRssFeedUrl(cleanUrl)
                        logger.log(`Successfully retrieved RSS feed URL: ${feedUrl}`)
                    } catch (err) {
                        console.error('Error getting RSS feed URL:', err)
                        // Fallback to default Substack RSS feed pattern
                        feedUrl = `${cleanUrl}/feed`
                        logger.log('Using default feed URL:', feedUrl)
                    }

                    if (!feedUrl) {
                        throw new Error('Could not determine RSS feed URL')
                    }

                    // Add to selected publications (using same format as SearchModal)
                    const newPub = {
                        id: handle,
                        name: publicationName,
                        title: publicationName,
                        url: cleanUrl,
                        publisher: publisher,
                        feed_url: feedUrl,
                        handle: handle,
                    }
                    addPublication(newPub)

                    // Also create/find the publication in the database
                    try {
                        logger.log('Creating/finding publication in database:', { title: publicationName, url: cleanUrl })

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
                            logger.log('Publication created/found in database:', pubData.publication)

                            // Update publication with database ID and trigger preview fetch
                            if (pubData.publication?.id && onPublicationAdded) {
                                const oldId = newPub.id;
                                newPub.id = pubData.publication.id;

                                // Update the ID in selectedPublications context
                                updatePublicationId(oldId, pubData.publication.id);

                                // Wait for context update to complete
                                await new Promise(resolve => setTimeout(resolve, 100));

                                onPublicationAdded(newPub);
                            }
                        } else {
                            const errorText = await pubResponse.text()
                            console.error('Failed to create publication in database:', errorText)
                            logger.warn(`Database operation failed but publication added to context: ${errorText}`)
                        }
                    } catch (dbErr) {
                        console.error('Error creating publication in database:', dbErr)
                        logger.warn('Database operation failed but publication added to context')
                        // Don't fail the whole operation if DB insert fails
                    }

                    addedCount++
                    logger.log(`Successfully added publication: ${publicationName}`)
                } catch (err) {
                    console.error(`Failed to add URL ${url}:`, err)
                    failed.push({ url, reason: err.message || 'Unknown error' })
                    logger.error(`Failed to process ${url}:`, err)
                    // Continue with other URLs
                }
            }

            setSuccessCount(addedCount)
            setFailedUrls(failed)

            if (addedCount > 0) {
                logger.log(`Successfully added ${addedCount} publication(s)`)

                // Clear input and close modal after a brief delay
                setTimeout(() => {
                    setUrlInput('')
                    setSuccessCount(0)
                    setFailedUrls([])
                    onClose()
                }, 2000)
            } else {
                setError('Failed to add any publications. Please check the URLs and try again.')
                logger.error('No publications were successfully added')
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
            setFailedUrls([])
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
                bgcolor: 'var(--white)',
                border: '2px solid var(--black)',
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
                        color: 'var(--black)'
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
                                borderColor: 'var(--black)',
                                borderWidth: '2px'
                            },
                            '&:hover fieldset': {
                                borderColor: 'var(--primary)'
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: 'var(--primary)'
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

                {failedUrls.length > 0 && (
                    <Alert
                        severity="warning"
                        sx={{
                            mb: 2,
                            backgroundColor: '#fff3e0',
                            color: '#e65100',
                            border: '1px solid #e65100',
                            '& .MuiAlert-icon': {
                                color: '#e65100'
                            }
                        }}
                    >
                        <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                            Failed to add {failedUrls.length} URL{failedUrls.length !== 1 ? 's' : ''}:
                        </Typography>
                        {failedUrls.map((failure, idx) => (
                            <Typography key={idx} variant="caption" component="div" sx={{ mt: 0.5 }}>
                                • {failure.url}: {failure.reason}
                            </Typography>
                        ))}
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
                            color: 'var(--black)',
                            borderColor: 'var(--black)',
                            borderWidth: '2px',
                            px: 3,
                            '&:hover': {
                                borderColor: 'var(--black)',
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
                            backgroundColor: 'var(--primary)',
                            color: 'var(--white)',
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
