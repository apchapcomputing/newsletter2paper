'use client'

import { Collapse, Skeleton } from '@mui/material'

const squash = (text) => String(text || '').toLowerCase().replace(/[^a-z0-9]/g, '')

const formatDate = (dateString) => {
    const date = new Date(dateString)
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/**
 * What one publication would print: an inline summary for the row's single line (a count that
 * toggles the list, a quiet "No articles" note, a skeleton or an error) The list itself is the
 * named `ArticleList` export, which the row lays out under its header.
 */
export default function ArticlePreviewList({ publication, articles, status = 'loaded', error, windowLabel = 'this window', expanded = false, onToggle, onRetry }) {
    const name = publication?.title || publication?.name || 'this publication'

    if (status === 'loading') {
        return <Skeleton variant="text" width={110} height={20} aria-label="Loading articles" />
    }

    // Not asked yet (the paper is still being saved): say so rather than spinning or claiming zero.
    if (status === 'waiting') {
        return <span className="n2p-pub__note">Articles appear once the paper is saved</span>
    }

    const again = onRetry && (
        <>
            {' · '}
            <button type="button" className="n2p-pub__retry" onClick={onRetry}>{status === 'error' ? 'Try again' : 'Check again'}</button>
        </>
    )

    if (!articles || articles.length === 0) {
        if (status === 'error' || error) {
            return <span className="n2p-pub__note n2p-pub__note--error" role="alert" title={error}>Couldn&apos;t load articles{again}</span>
        }
        return <span className="n2p-pub__note">No articles {windowLabel}{again}</span>
    }

    return (
        <>
            <button
                type="button"
                className="n2p-pub__count"
                aria-expanded={expanded}
                aria-label={`${expanded ? 'Hide' : 'Show'} ${articles.length} article${articles.length !== 1 ? 's' : ''} from ${name}`}
                onClick={onToggle}
            >
                {articles.length} article{articles.length !== 1 ? 's' : ''}
            </button>
        </>
    )
}

/** The expanded article list; the row renders it under its header, outside the toggle's click area. */
export function ArticleList({ publication, articles, expanded = false }) {
    const name = publication?.title || publication?.name || ''
    if (!articles || articles.length === 0) return null
    return (
        <>
            <Collapse in={expanded} className="n2p-pub__list">
                <ul className="n2p-arts">
                    {articles.map((article, index) => (
                        <li key={article.id || index} className="n2p-art">
                            <a className="n2p-art__title" href={article.content_url} target="_blank" rel="noopener noreferrer">
                                {article.title}
                            </a>
                            <div className="n2p-art__meta">
                                {article.author && squash(article.author) !== squash(name) && <span>By {article.author}</span>}
                                {article.date_published && <span className="n2p-art__date">{formatDate(article.date_published)}</span>}
                            </div>
                            {article.subtitle && <p className="n2p-art__excerpt">{article.subtitle}</p>}
                        </li>
                    ))}
                </ul>
            </Collapse>
        </>
    )
}
