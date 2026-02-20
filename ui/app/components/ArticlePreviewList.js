'use client'

import { Box, Typography, Collapse, IconButton, Skeleton, Link as MuiLink } from '@mui/material'
import { useState } from 'react'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import ArticleIcon from '@mui/icons-material/Article'
import CalendarTodayIcon from '@mui/icons-material/CalendarToday'

export default function ArticlePreviewList({ publication, articles, isLoading, error }) {
    const [isExpanded, setIsExpanded] = useState(false)

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

    const toggleExpanded = () => {
        setIsExpanded(!isExpanded)
    }

    // If loading, show skeleton
    if (isLoading) {
        return (
            <Box sx={{ mt: 1 }}>
                <Skeleton variant="text" width="60%" height={20} />
                <Skeleton variant="text" width="80%" height={16} sx={{ mt: 0.4 }} />
                <Skeleton variant="text" width="75%" height={16} />
            </Box>
        )
    }

    // If no articles, show message
    if (!articles || articles.length === 0) {
        // If there's an error, show it
        if (error) {
            return (
                <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.813rem', color: 'error.main' }}>
                        Error loading articles: {error}
                    </Typography>
                </Box>
            )
        }

        return (
            <Box sx={{ mt: 1 }}>
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.813rem', fontStyle: 'italic' }}>
                    No recent articles found in the selected time frame
                </Typography>
            </Box>
        )
    }

    return (
        <Box sx={{ mt: 1 }}>
            {/* Header with article count */}
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    cursor: 'pointer',
                    '&:hover': {
                        opacity: 0.7
                    }
                }}
                onClick={toggleExpanded}
            >
                <ArticleIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                <Typography
                    variant="body2"
                    sx={{
                        fontSize: '0.875rem',
                        fontWeight: 500,
                        color: 'text.secondary'
                    }}
                >
                    {articles.length} article{articles.length !== 1 ? 's' : ''} to print
                </Typography>
                <IconButton
                    size="small"
                    sx={{
                        ml: 'auto',
                        p: 0.5
                    }}
                >
                    {isExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                </IconButton>
            </Box>

            {/* Article list */}
            <Collapse in={isExpanded}>
                <Box sx={{ mt: 1, px: 2 }}>
                    {articles.map((article, index) => (
                        <Box
                            key={article.id || index}
                            sx={{
                                py: 1,
                                borderBottom: index < articles.length - 1 ? '1px solid #e0e0e0' : 'none'
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
                                        color: 'primary.main'
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
            </Collapse >
        </Box >
    )
}
