'use client'

import { Box, Typography, Collapse, Skeleton, Link as MuiLink } from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import CalendarTodayIcon from '@mui/icons-material/CalendarToday'

/**
 * What one publication would print: an inline summary for the row's single line (a count that
 * toggles the list, a quiet "0 articles" note, a skeleton or an error) and the list itself, which
 * the row lays out below its line. Rendered as siblings so the row stays one flex container.
 */
export default function ArticlePreviewList({ publication, articles, status = 'loaded', error, windowLabel = 'this window', expanded = false, onToggle, onRetry }) {
    const name = publication?.title || publication?.name || 'this publication'

    const formatDate = (dateString) => {
        try {
            const date = new Date(dateString)
            return date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
            })
        } catch {
            return dateString
        }
    }

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
        return <span className="n2p-pub__note">0 articles {windowLabel}{again}</span>
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
                {expanded ? <ExpandLessIcon fontSize="small" aria-hidden="true" /> : <ExpandMoreIcon fontSize="small" aria-hidden="true" />}
            </button>

            {/* Article list */}
            <Collapse in={expanded} className="n2p-pub__list">
                <Box sx={{ mt: 1, px: 2 }}>
                    {articles.map((article, index) => (
                        <Box
                            key={article.id || index}
                            sx={{
                                py: 1,
                                borderBottom: index < articles.length - 1 ? 'var(--rule) solid var(--line)' : 'none'
                            }}
                        >
                            {/* Article title with link */}
                            <MuiLink
                                href={article.content_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                underline="hover"
                                sx={{
                                    display: 'block',
                                    fontSize: '0.875rem',
                                    fontWeight: 500,
                                    color: 'text.primary',
                                    mb: 0.5,
                                    '&:hover': {
                                        color: 'secondary.main'
                                    }
                                }}
                            >
                                {article.title}
                            </MuiLink>

                            {/* Article metadata */}
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                                {article.author && (
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            fontSize: '0.75rem',
                                            color: 'text.secondary'
                                        }}
                                    >
                                        By {article.author}
                                    </Typography>
                                )}
                                {article.date_published && (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                        <CalendarTodayIcon sx={{ fontSize: '0.75rem', color: 'text.secondary' }} />
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                fontSize: '0.75rem',
                                                color: 'text.secondary'
                                            }}
                                        >
                                            {formatDate(article.date_published)}
                                        </Typography>
                                    </Box>
                                )}
                            </Box>

                            {/* Article subtitle/description */}
                            {article.subtitle && (
                                <Typography
                                    variant="caption"
                                    sx={{
                                        display: 'block',
                                        fontSize: '0.75rem',
                                        color: 'text.secondary',
                                        mt: 0.5,
                                        lineHeight: 1.3
                                    }}
                                >
                                    {article.subtitle.length > 150
                                        ? `${article.subtitle.substring(0, 150)}...`
                                        : article.subtitle
                                    }
                                </Typography>
                            )}
                        </Box>
                    ))}
                </Box>
            </Collapse>
        </>
    )
}
