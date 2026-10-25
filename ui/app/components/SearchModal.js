import Modal from '@mui/material/Modal';
import { track } from '../../lib/analytics';
import Paper from '@mui/material/Paper';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import ListItemAvatar from '@mui/material/ListItemAvatar';
import Avatar from '@mui/material/Avatar';
import Checkbox from '@mui/material/Checkbox';
import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';

import SearchHistory from './SearchHistory';

import { getRssFeedUrl } from '../../utils/rssUtils';
import { searchSubstack } from '../../utils/substackUtils';
import logger from '../../utils/logger';

import { useSelectedPublications } from '../../contexts/useSelectedPublications';

export default function SearchModal({
    isOpen,
    onClose,
    searchQuery,
    onSearchQueryChange,
    searchResults,
    searchHistory,
    onSelectHistory,
    onRemoveFromHistory,
    onPublicationAdded
}) {
    const { selectedPublications, addPublication, removePublication, updatePublicationId } = useSelectedPublications();

    const handlePublicationToggle = async (searchResult) => {
        try {
            // if result is type user, make a secondary search with the publication's name to get the publication domain
            logger.log('res', searchResult)

            let url;
            if (searchResult.type === 'publication') {
                url = searchResult.domain;
            } else if (searchResult.type === 'user') {
                // For user results, construct the URL from their handle
                // Substack user publications are typically at: username.substack.com
                if (searchResult.handle) {
                    url = `https://${searchResult.handle}.substack.com`;
                } else {
                    // Fallback: search for the publication to get the domain
                    const results = await searchSubstack(searchResult.name);
                    const publicationResult = results.find(r => r.type === 'publication');
                    if (publicationResult) {
                        url = publicationResult.domain;
                    }
                }
            }

            // Ensure URL has https:// prefix
            if (url && !url.startsWith('http')) {
                url = `https://${url}`;
            }

            if (!url) {
                console.error('Could not determine URL for publication:', searchResult);
                return;
            }

            logger.log('Publication URL:', url);

            // Get RSS feed URL with error handling
            let feedUrl;
            try {
                feedUrl = await getRssFeedUrl(url);
            } catch (error) {
                console.error('Error getting RSS feed URL:', error);
                // Fallback to default Substack RSS feed pattern
                feedUrl = `${url}/feed`;
                logger.log('Using default feed URL:', feedUrl);
            }

            // Check if already selected (using temporary ID for now)
            const tempId = searchResult.handle || searchResult.subdomain || `pub-${Date.now()}`;
            const isAlreadySelected = selectedPublications.some(p =>
                p.id === tempId || p.handle === searchResult.handle
            );

            if (isAlreadySelected) {
                // Find publication by handle or temp ID
                const pubToRemove = selectedPublications.find(p =>
                    p.id === tempId || p.handle === searchResult.handle
                );
                if (pubToRemove) {
                    removePublication(pubToRemove.id);
                }
            } else {
                // Create/find publication in database FIRST to get real UUID
                let publicationId = tempId;

                try {
                    const pubResponse = await fetch('/api/publications-db?action=find-or-create', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            title: searchResult.name,
                            url: url,
                            rss_feed_url: feedUrl,
                            publisher: searchResult.publisher || searchResult.handle || 'Unknown Author'
                        })
                    });

                    if (pubResponse.ok) {
                        const pubData = await pubResponse.json();
                        logger.log('Publication created/found in database:', pubData.publication);
                        publicationId = pubData.publication.id;
                    } else {
                        console.error('Failed to create publication in database, using temp ID');
                    }
                } catch (dbErr) {
                    console.error('Error creating publication in database:', dbErr);
                }

                // Now add publication to context with real UUID
                const publication = {
                    id: publicationId,  // Real UUID from database
                    name: searchResult.name,
                    title: searchResult.name,
                    url: url,
                    publisher: searchResult.publisher || searchResult.handle || 'Unknown Author',
                    feed_url: feedUrl,
                    handle: searchResult.handle || searchResult.subdomain,
                };

                addPublication(publication);
                track('publication_added', { source: 'search' });

                // Trigger preview fetch if callback provided
                if (onPublicationAdded && publicationId !== tempId) {
                    // Wait for context update
                    await new Promise(resolve => setTimeout(resolve, 100));
                    onPublicationAdded(publication);
                }
            }
        } catch (error) {
            console.error('Error toggling publication:', error);
        }
    };

    const isPublicationSelected = (searchResult) => {
        const publicationId = searchResult.handle || searchResult.subdomain;
        return selectedPublications.some(p => p.id === publicationId);
    };
    const rowSecondary = (result) =>
        `${result.type === 'user' ? `@${result.handle}` : result.subdomain}${result.subscribers ? ` • ${result.subscribers}` : ''}`;

    return (
        <Modal
            open={isOpen}
            onClose={onClose}
            sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'center', p: { xs: 2, sm: 0 }, pt: { xs: 2, sm: 10 } }}
        >
            <Paper
                role="dialog"
                aria-modal="true"
                aria-labelledby="search-modal-title"
                sx={{
                    width: '100%',
                    maxWidth: 600,
                    maxHeight: 'calc(100vh - 32px)',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                    backgroundColor: 'var(--paper-raised)',
                    border: '2px solid var(--ink)',
                    boxShadow: 'var(--shadow-stamp)',
                }}
            >
                {/* Title bar, as on the step window */}
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pl: 2, bgcolor: 'var(--primary)', borderBottom: '2px solid var(--ink)' }}>
                    <Box component="h2" id="search-modal-title" sx={{ m: 0, font: '700 14px/20px var(--font-display)', textTransform: 'uppercase' }}>
                        Search Substack
                    </Box>
                    <IconButton onClick={onClose} aria-label="Close search" size="small" sx={{ m: 0.5 }}>
                        <CloseIcon />
                    </IconButton>
                </Box>

                <Box sx={{ p: 3, pb: 2 }}>
                    <TextField
                        fullWidth
                        variant="outlined"
                        placeholder="People, publications, or topics"
                        value={searchQuery}
                        onChange={(e) => onSearchQueryChange(e.target.value)}
                        autoFocus
                        slotProps={{
                            htmlInput: { 'aria-label': 'Search Substack for people, publications, or topics' },
                            input: {
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchIcon sx={{ color: 'var(--ink-muted)' }} />
                                    </InputAdornment>
                                ),
                            },
                        }}
                    />
                </Box>

                <Box sx={{ px: 3, pb: 3, minHeight: 240, overflow: 'auto' }} aria-live="polite">
                    {searchResults.length > 0 ? (
                        <List disablePadding aria-label="Search results">
                            {searchResults.map((result, index) => (
                                <ListItem key={index} disablePadding>
                                    <ListItemButton onClick={() => handlePublicationToggle(result)} sx={{ '&:hover': { bgcolor: 'var(--secondary-soft)' } }}>
                                        <ListItemAvatar>
                                            <Avatar sx={{ backgroundColor: 'secondary.main', color: 'secondary.contrastText', fontWeight: 'medium' }}>
                                                {(result.name && result.name.length > 0) ? result.name.charAt(0).toUpperCase() : '?'}
                                            </Avatar>
                                        </ListItemAvatar>
                                        <ListItemText primary={result.name} secondary={rowSecondary(result)} />
                                        <Checkbox
                                            edge="end"
                                            tabIndex={-1}
                                            checked={isPublicationSelected(result)}
                                            slotProps={{ input: { 'aria-label': `Include ${result.name}` } }}
                                            sx={{ pointerEvents: 'none' }}
                                        />
                                    </ListItemButton>
                                </ListItem>
                            ))}
                        </List>
                    ) : (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                            {selectedPublications.length > 0 && (
                                <Box component="section" aria-labelledby="search-selected-heading">
                                    <Box component="h3" id="search-selected-heading" className="n2p-label-sm" sx={{ m: 0, mb: 1, color: 'var(--secondary)' }}>
                                        In this issue
                                    </Box>
                                    <List disablePadding>
                                        {selectedPublications.slice(0, 5).map((publication, index) => (
                                            <ListItem key={publication.id || index} disablePadding>
                                                <ListItemButton onClick={() => removePublication(publication.id)} sx={{ '&:hover': { bgcolor: 'var(--secondary-soft)' } }}>
                                                    <ListItemAvatar>
                                                        <Avatar sx={{ backgroundColor: 'primary.main', color: 'primary.contrastText', fontWeight: 'medium' }}>
                                                            {(publication.name || publication.title || '').charAt(0).toUpperCase() || '?'}
                                                        </Avatar>
                                                    </ListItemAvatar>
                                                    <ListItemText
                                                        primary={publication.name || publication.title}
                                                        secondary={publication.subscribers ? `${publication.subscribers}` : (publication.handle ? `@${publication.handle}` : publication.url)}
                                                    />
                                                    <Checkbox
                                                        edge="end"
                                                        tabIndex={-1}
                                                        checked
                                                        slotProps={{ input: { 'aria-label': `Remove ${publication.name || publication.title}` } }}
                                                        sx={{ pointerEvents: 'none' }}
                                                    />
                                                </ListItemButton>
                                            </ListItem>
                                        ))}
                                    </List>
                                </Box>
                            )}

                            <SearchHistory
                                searchHistory={searchHistory}
                                onSelectHistory={onSelectHistory}
                                onRemoveFromHistory={onRemoveFromHistory}
                            />
                        </Box>
                    )}
                </Box>
            </Paper>
        </Modal>
    );
}
