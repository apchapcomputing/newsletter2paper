'use client'

import { useState, useImperativeHandle, forwardRef } from 'react'
import { Tooltip, CircularProgress, Checkbox, FormControlLabel } from '@mui/material'
import ImageIcon from '@mui/icons-material/Image'
import HideImageIcon from '@mui/icons-material/HideImage'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'
import AddUrlModal from './AddUrlModal'
import ArticlePreviewList, { ArticleList } from './ArticlePreviewList'
import PullQuote from './PullQuote'
import logger from '../../utils/logger'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// The author line is only worth a second name when it says something the title does not.
const squash = (text) => (text || '').toLowerCase().replace(/[^a-z0-9]/g, '')
const authorLine = (title, author) => (author && squash(author) !== squash(title) ? author : '')

// Step 1: choose the newsletters. Each one reads as a byline with the articles it would print.
const AddPublications = forwardRef(({ onOpenSearch, onSaveIssue, isPopulatingPublications = false, previews, windowLabel }, ref) => {
    const { selectedPublications, removePublication, toggleRemoveImages } = useSelectedPublications()

    // One switch for the whole paper; each row's own toggle can still differ.
    const allImagesRemoved = selectedPublications.length > 0 && selectedPublications.every(pub => pub.remove_images === true)
    const someImagesRemoved = selectedPublications.some(pub => pub.remove_images === true) && !allImagesRemoved
    const handleToggleAllImages = (event) => {
        const target = event.target.checked
        selectedPublications.forEach(pub => {
            if (Boolean(pub.remove_images) !== target) toggleRemoveImages(pub.id || pub.name)
        })
    }

    const [isUrlModalOpen, setIsUrlModalOpen] = useState(false)
    const [openIds, setOpenIds] = useState(() => new Set())
    const toggleOpen = (id) => setOpenIds(prev => {
        const next = new Set(prev)
        if (!next.delete(id)) next.add(id)
        return next
    })

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

        // The publication has to be linked to a saved issue before its articles can be listed.
        if (onSaveIssue) {
            logger.log('💾 Saving issue before fetching preview...')
            await onSaveIssue()

            // Add buffer for database replication
            await new Promise(resolve => setTimeout(resolve, 300))
        }

        // Fetch articles for this publication only. `force` replaces any request the effect already
        // started before the link existed, so an early empty answer cannot stand.
        previews.fetchFor(publication.id, { force: true })
    }

    const handleRemovePublication = (pubId) => {
        removePublication(pubId)
        previews.forget(pubId)
    }

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

                {selectedPublications.length > 0 && (
                    <FormControlLabel
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
                )}

                {selectedPublications.length > 0 ? (
                    <div className="n2p-pubs" aria-labelledby="in-issue-label" role="list">
                        {selectedPublications.map((publication, index) => {
                            const name = publication.name || publication.title
                            const pubState = previews.previewFor(publication.id)
                            const removeImages = Boolean(publication.remove_images)
                            const isOpen = openIds.has(publication.id)
                            const hasArticles = (pubState.articles?.length || 0) > 0
                            const author = authorLine(name, publication.publisher || publication.handle)

                            return (
                                <div className={`n2p-pub${isOpen ? ' is-open' : ''}`} role="listitem" key={publication.id || index}>
                                    <div className="n2p-pub__head">
                                    <div className="n2p-pub__main">
                                        <a href={publication.url} target="_blank" rel="noopener noreferrer">
                                            <b className="n2p-pub__name">{name}</b>
                                            {author && <span className="n2p-pub__dl">{author}</span>}
                                        </a>
                                    </div>

                                    <ArticlePreviewList
                                        publication={publication}
                                        articles={pubState.articles}
                                        status={pubState.status}
                                        error={pubState.error}
                                        onRetry={() => previews.retry(publication.id)}
                                        windowLabel={windowLabel}
                                        expanded={isOpen}
                                        onToggle={() => toggleOpen(publication.id)}
                                    />

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

                                    <span className={`n2p-pub__chev${hasArticles ? '' : ' is-empty'}`} aria-hidden="true">
                                        {isOpen ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                                    </span>
                                    </div>

                                    <ArticleList publication={publication} articles={pubState.articles} expanded={isOpen} />
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
