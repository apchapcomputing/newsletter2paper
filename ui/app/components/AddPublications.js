'use client'

import { useState, useImperativeHandle, forwardRef } from 'react'
import { Checkbox, FormControlLabel, Tooltip, CircularProgress } from '@mui/material'
import ImageIcon from '@mui/icons-material/Image'
import HideImageIcon from '@mui/icons-material/HideImage'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'
import AddUrlModal from './AddUrlModal'
import ArticlePreviewList from './ArticlePreviewList'
import PullQuote from './PullQuote'
import logger from '../../utils/logger'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// Step 1: choose the newsletters. Each one reads as a byline with the articles it would print.
const AddPublications = forwardRef(({ onOpenSearch, onSaveIssue, isSaving: isSavingProp, isPopulatingPublications = false, previews }, ref) => {
    const { selectedPublications, removePublication, toggleRemoveImages } = useSelectedPublications()
    const [isUrlModalOpen, setIsUrlModalOpen] = useState(false)

    // Expose handlePublicationAdded to parent via ref
    useImperativeHandle(ref, () => ({
        handlePublicationAdded
    }))

    // Handle publication added - this will be called from modals
    const handlePublicationAdded = async (publication) => {
        if (!publication?.id) {
            logger.error('Publication missing ID:', publication)
            return
        }

        // Validate that we have a UUID, not a temporary ID
        if (!UUID_RE.test(publication.id)) {
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
        previews.fetchFor(publication.id)
    }

    const handleRemovePublication = (pubId) => {
        removePublication(pubId)
        previews.forget(pubId)
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
        <>
            <div className="n2p-field">
                <span className="n2p-label" id="add-source-label">Add a publication</span>
                <div className="n2p-row" role="group" aria-labelledby="add-source-label" style={{ marginTop: 'var(--space-2)' }}>
                    <button type="button" className="n2p-btn" onClick={onOpenSearch}>Search Substack</button>
                    <button type="button" className="n2p-btn" onClick={() => setIsUrlModalOpen(true)}>Add via link</button>
                </div>
            </div>

            <div className="n2p-field" style={{ marginBottom: 0 }}>
                <div className="n2p-count-line">
                    <span className="n2p-label" id="in-issue-label">In this issue</span>
                    <span className="n2p-sticker n2p-sticker--hot" aria-label={`${selectedPublications.length} selected`}>{selectedPublications.length}</span>
                </div>

                {/* Master checkbox to toggle all (only show if there are publications) */}
                {selectedPublications.length > 0 && (
                    <Tooltip
                        title="Toggle image removal for all publications at once. You can then adjust individual publications as needed."
                        placement="right"
                    >
                        <FormControlLabel
                            sx={{ mb: 1 }}
                            control={
                                <Checkbox
                                    checked={allImagesRemoved}
                                    indeterminate={someImagesRemoved}
                                    onChange={handleToggleAllImages}
                                    size="small"
                                />
                            }
                            label="Remove images from all publications"
                            slotProps={{ typography: { variant: 'body2' } }}
                        />
                    </Tooltip>
                )}

                {selectedPublications.length > 0 ? (
                    <div aria-labelledby="in-issue-label" role="list">
                        {selectedPublications.map((publication, index) => {
                            const name = publication.name || publication.title
                            const pubState = previews.previewFor(publication.id)
                            const removeImages = Boolean(publication.remove_images)

                            return (
                                <div className="n2p-pub n2p-pub--stack" role="listitem" key={publication.id || index}>
                                    <div className="n2p-pub__main">
                                        <a href={publication.url} target="_blank" rel="noopener noreferrer">
                                            <div className="n2p-pub__by">By <b className="n2p-pub__name">{name}</b></div>
                                            <div className="n2p-pub__dl">{publication.publisher || publication.handle || publication.url}</div>
                                        </a>
                                    </div>

                                    <div className="n2p-pub__tools">
                                        <Tooltip title={removeImages ? 'Images will be removed from this publication' : 'Images will be included from this publication'} placement="top">
                                            <button
                                                type="button"
                                                className="n2p-pub__x"
                                                aria-pressed={removeImages}
                                                aria-label={`Remove images from ${name}`}
                                                onClick={() => toggleRemoveImages(publication.id || publication.name)}
                                            >
                                                {removeImages ? <HideImageIcon fontSize="small" /> : <ImageIcon fontSize="small" />}
                                            </button>
                                        </Tooltip>
                                        <button
                                            type="button"
                                            className="n2p-pub__x"
                                            aria-label={`Remove ${name}`}
                                            onClick={() => handleRemovePublication(publication.id || publication.name)}
                                        >
                                            ×
                                        </button>
                                    </div>

                                    <div className="n2p-pub__articles">
                                        <ArticlePreviewList
                                            publication={publication}
                                            articles={pubState.articles}
                                            isLoading={pubState.status === 'loading'}
                                            error={pubState.error}
                                        />
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                ) : isPopulatingPublications ? (
                    <p className="n2p-help" role="status" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                        <CircularProgress size={18} sx={{ color: 'var(--primary-deep)' }} />
                        Loading saved publications…
                    </p>
                ) : (
                    <PullQuote quote="A paper with no writers is just paper." cite="Add a newsletter to start the presses" />
                )}
            </div>

            {/* Add URL Modal */}
            <AddUrlModal
                open={isUrlModalOpen}
                onClose={() => setIsUrlModalOpen(false)}
                onPublicationAdded={handlePublicationAdded}
            />
        </>
    )
})

AddPublications.displayName = 'AddPublications'

export default AddPublications
