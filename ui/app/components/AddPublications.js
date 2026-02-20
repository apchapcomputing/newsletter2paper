'use client'

import { useState, useEffect, useImperativeHandle, forwardRef } from 'react'
import { Box, Typography, Button, Checkbox, FormControlLabel, Tooltip } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import ImageIcon from '@mui/icons-material/Image'
import HideImageIcon from '@mui/icons-material/HideImage'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'
import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'
import AddUrlModal from './AddUrlModal'
import ArticlePreviewList from './ArticlePreviewList'
import logger from '../../utils/logger'

const AddPublications = forwardRef(({ onOpenSearch, onSaveIssue, isSaving: isSavingProp }, ref) => {
    const { selectedPublications, removePublication, toggleRemoveImages } = useSelectedPublications()
    const { outputMode, frequency, currentIssueId } = useNewsletterConfig()
    const [isUrlModalOpen, setIsUrlModalOpen] = useState(false)

    // Per-publication state tracking: {pubId: {status: 'loading'|'loaded'|'error', articles: [], error: ''}}
    const [publicationStates, setPublicationStates] = useState({})

    // Only show remove images option for essay format
    const showImageOptions = outputMode === 'essay'

    // Expose handlePublicationAdded to parent via ref
    useImperativeHandle(ref, () => ({
        handlePublicationAdded
    }))

    // Auto-fetch article previews when publications are loaded (e.g., from database on issue select)
    useEffect(() => {
        if (!currentIssueId) return

        // UUID validation regex
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

        // Find publications that need preview data fetched
        selectedPublications.forEach(pub => {
            const pubId = pub.id
            const currentState = publicationStates[pubId]

            // Validate UUID before fetching
            if (!uuidRegex.test(pubId)) {
                logger.warn(`⚠️ Skipping preview fetch for publication with invalid UUID: ${pubId}`)
                return
            }

            // Only fetch if we don't have state for this publication yet
            if (!currentState) {
                logger.log(`🔄 Auto-fetching preview for loaded publication: ${pub.name || pub.title} (${pubId})`)
                fetchArticlesForPublication(pubId)
            }
        })
    }, [selectedPublications, currentIssueId])

    // Fetch articles for a single publication with retry logic
    const fetchArticlesForPublication = async (pubId, retryCount = 0) => {
        const maxRetries = 3
        const retryDelays = [500, 1000, 2000] // Exponential backoff

        if (!currentIssueId || !pubId) {
            logger.log('⚠️ Missing issue ID or publication ID, skipping fetch')
            return
        }

        // Set loading state
        setPublicationStates(prev => ({
            ...prev,
            [pubId]: { status: 'loading', articles: [], error: '' }
        }))

        try {
            // Map frequency to days_back parameter
            const frequencyToDays = {
                'daily': 1,
                'weekly': 7,
                'monthly': 30
            }
            const daysBack = frequencyToDays[frequency] || 7

            const response = await fetch(
                `/api/articles/preview/${currentIssueId}?days_back=${daysBack}&publication_id=${pubId}`
            )

            if (!response.ok) {
                const errorText = await response.text()
                logger.error(`Failed to fetch previews (${response.status}):`, errorText)
                throw new Error(`Failed to fetch article previews: ${response.status} ${response.statusText}`)
            }

            const result = await response.json()

            if (result.success && result.data) {
                const articles = result.data.articles_by_publication?.[pubId] || []

                // Check if we got empty results but the publication exists in selectedPublications
                const pubExists = selectedPublications.some(p => p.id === pubId)

                if (articles.length === 0 && pubExists && retryCount < maxRetries) {
                    // Retry with exponential backoff
                    logger.log(`🔄 Retry ${retryCount + 1}/${maxRetries} for publication ${pubId} after ${retryDelays[retryCount]}ms`)
                    setTimeout(() => {
                        fetchArticlesForPublication(pubId, retryCount + 1)
                    }, retryDelays[retryCount])
                    return
                }

                // Success - update state
                setPublicationStates(prev => ({
                    ...prev,
                    [pubId]: { status: 'loaded', articles, error: '' }
                }))

                logger.log(`✅ Loaded ${articles.length} articles for publication ${pubId}`)
                logger.log(`📦 Updated publicationStates for ${pubId}:`, { status: 'loaded', articles: articles.length })
            } else {
                setPublicationStates(prev => ({
                    ...prev,
                    [pubId]: { status: 'loaded', articles: [], error: '' }
                }))
            }
        } catch (error) {
            logger.error(`Error fetching articles for publication ${pubId}:`, error)
            setPublicationStates(prev => ({
                ...prev,
                [pubId]: { status: 'error', articles: [], error: error.message }
            }))
        }
    }

    // Handle publication added - this will be called from modals
    const handlePublicationAdded = async (publication) => {
        if (!publication?.id) {
            logger.error('Publication missing ID:', publication)
            return
        }

        // Validate that we have a UUID, not a temporary ID
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
        if (!uuidRegex.test(publication.id)) {
            logger.error('❌ Publication has invalid UUID:', publication.id, '- skipping preview fetch')
            logger.error('Publication object:', publication)
            return
        }

        logger.log(`📰 Publication added: ${publication.name || publication.title} (ID: ${publication.id})`)

        // Wait for save to complete
        if (onSaveIssue) {
            logger.log('💾 Saving issue before fetching preview...')
            await onSaveIssue()

            // Wait for save prop to become false
            let waitCount = 0
            while (isSavingProp && waitCount < 30) { // Max 3 seconds
                await new Promise(resolve => setTimeout(resolve, 100))
                waitCount++
            }

            // Add buffer for database replication
            await new Promise(resolve => setTimeout(resolve, 300))
        }

        // Fetch articles for this publication only
        fetchArticlesForPublication(publication.id)
    }

    // Clean up state when publication is removed
    const handleRemovePublication = (pubId) => {
        removePublication(pubId)

        // Remove from publicationStates to prevent memory leaks
        setPublicationStates(prev => {
            const next = { ...prev }
            delete next[pubId]
            return next
        })
    }

    // Handle master checkbox to toggle all publications
    const handleToggleAllImages = (event) => {
        const isChecked = event.target.checked
        selectedPublications.forEach(pub => {
            const currentState = pub.remove_images || false
            // Only toggle if the current state is different from target state
            if (currentState !== isChecked) {
                toggleRemoveImages(pub.id || pub.name)
            }
        })
    }

    // Check if all publications have remove_images enabled
    const allImagesRemoved = selectedPublications.length > 0 &&
        selectedPublications.every(pub => pub.remove_images === true)

    // Check if some (but not all) have remove_images enabled
    const someImagesRemoved = selectedPublications.some(pub => pub.remove_images === true) && !allImagesRemoved

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
                Add Publications
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
                Add Substack publications to print in your newspaper
            </Typography>

            <Box sx={{
                width: '100%',
                height: '2px',
                backgroundColor: 'var(--black)',
                mb: 3
            }} />

            {/* Add Publication Source Controls */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                    ADD PUBLICATION SOURCE
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', sm: 'row' } }}>
                    <Button
                        variant="contained"
                        onClick={onOpenSearch}
                        sx={{
                            flex: 1,
                            py: 1.5,
                            fontWeight: 'medium',
                            textTransform: 'none',
                            fontSize: '1rem',
                            backgroundColor: '#f5f5f5',
                            color: '#291D18',
                            border: '1px solid #ccc',
                            '&:hover': {
                                borderColor: '#291D18'
                            }
                        }}
                    >
                        SEARCH
                    </Button>
                    <Button
                        variant="contained"
                        onClick={() => setIsUrlModalOpen(true)}
                        sx={{
                            flex: 1,
                            py: 1.5,
                            fontWeight: 'medium',
                            textTransform: 'none',
                            fontSize: '1rem',
                            backgroundColor: '#f5f5f5',
                            color: '#291D18',
                            border: '1px solid #ccc',
                            '&:hover': {
                                borderColor: '#291D18'
                            }
                        }}
                    >
                        ADD VIA URL
                    </Button>
                </Box>
            </Box>

            {/* Publications to Print */}
            <Box>
                <Typography variant="body1" sx={{ fontWeight: 500, mb: 2 }}>
                    PUBLICATIONS TO PRINT
                </Typography>

                {/* Master checkbox to toggle all (only show if there are publications and essay mode) */}
                {showImageOptions && selectedPublications.length > 0 && (
                    <Box sx={{ mb: 2, pl: 1 }}>
                        <Tooltip
                            title="Toggle image removal for all publications at once. You can then adjust individual publications as needed."
                            placement="right"
                        >
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={allImagesRemoved}
                                        indeterminate={someImagesRemoved}
                                        onChange={handleToggleAllImages}
                                        size="small"
                                        sx={{
                                            color: 'var(--primary)',
                                            '&.Mui-checked': {
                                                color: 'var(--primary)',
                                            },
                                            '&.MuiCheckbox-indeterminate': {
                                                color: 'var(--primary)',
                                            },
                                        }}
                                    />
                                }
                                label={
                                    <Typography variant="body2" sx={{ fontSize: '0.875rem', fontWeight: 500 }}>
                                        Remove images from all publications
                                    </Typography>
                                }
                            />
                        </Tooltip>
                    </Box>
                )}

                {/* Selected Publications List */}
                {selectedPublications.length > 0 ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        {selectedPublications.map((publication, index) => {
                            // Get publication state (articles, loading, error)
                            const pubState = publicationStates[publication.id] || {
                                status: 'loading',
                                articles: [],
                                error: ''
                            }

                            // Debug logging
                            if (pubState.status !== 'loading') {
                                logger.log(`📊 Publication ${publication.name} (${publication.id}): ${pubState.status}, ${pubState.articles.length} articles`)
                            }

                            return (
                                <Box
                                    key={publication.id || index}
                                    sx={{
                                        display: 'flex',
                                        flexDirection: 'column',
                                        p: 2,
                                        backgroundColor: '#f5f5f5',
                                        border: '1px solid #ccc'
                                    }}
                                >
                                    {/* Publication Header with Title and Remove Button */}
                                    <Box sx={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'flex-start',
                                        mb: showImageOptions ? 1 : 0
                                    }}>
                                        <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                                            <Typography variant="body1" sx={{ fontWeight: 500 }}>
                                                {publication.name || publication.title}
                                            </Typography>
                                            <Typography variant="body2" color="text.secondary">
                                                {publication.publisher || publication.handle || publication.url}
                                            </Typography>
                                        </Box>

                                        {
                                            showImageOptions && (
                                                <Tooltip
                                                    title={publication.remove_images ? "Images will be removed from this publication" : "Images will be included from this publication"}
                                                    placement="top"
                                                >
                                                    <Button
                                                        onClick={() => toggleRemoveImages(publication.id || publication.name)}
                                                        sx={{
                                                            minWidth: '30px',
                                                            width: '30px',
                                                            height: '30px',
                                                            p: 0,
                                                            mr: 2,
                                                            borderRadius: 0,
                                                            backgroundColor: '#f5f5f5',
                                                            color: publication.remove_images ? 'text.secondary' : 'var(--primary)',
                                                            '&:hover': {
                                                                backgroundColor: '#e0e0e0',
                                                                borderColor: 'var(--primary)',
                                                            }
                                                        }}
                                                    >
                                                        {publication.remove_images ? (
                                                            <HideImageIcon fontSize="small" />
                                                        ) : (
                                                            <ImageIcon fontSize="small" />
                                                        )}
                                                    </Button>
                                                </Tooltip>
                                            )
                                        }

                                        <Button
                                            onClick={() => handleRemovePublication(publication.id || publication.name)}
                                            sx={{
                                                minWidth: '32px',
                                                width: '32px',
                                                height: '32px',
                                                p: 0,
                                                borderRadius: 0,
                                                color: 'text.secondary',
                                                '&:hover': {
                                                    color: '#9E2A2B', // Error red dark
                                                    backgroundColor: 'rgba(158, 42, 43, 0.04)',
                                                }
                                            }}
                                        >
                                            <CloseIcon fontSize="small" />
                                        </Button>
                                    </Box>

                                    {/* Article Preview List */}
                                    <ArticlePreviewList
                                        publication={publication}
                                        articles={pubState.articles}
                                        isLoading={pubState.status === 'loading'}
                                        error={pubState.error}
                                    />
                                </Box>
                            )
                        })}
                    </Box>
                ) : (
                    <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                        No publications selected yet. Use the search or add URL options above to add publications.
                    </Typography>
                )}
            </Box>

            {/* Add URL Modal */}
            <AddUrlModal
                open={isUrlModalOpen}
                onClose={() => setIsUrlModalOpen(false)}
                onPublicationAdded={handlePublicationAdded}
            />
        </Box >
    )
})

AddPublications.displayName = 'AddPublications'

export default AddPublications