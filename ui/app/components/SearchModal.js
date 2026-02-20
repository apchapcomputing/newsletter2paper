import Modal from '@mui/material/Modal';
import Paper from '@mui/material/Paper';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import ListItemAvatar from '@mui/material/ListItemAvatar';
import Avatar from '@mui/material/Avatar';
import Checkbox from '@mui/material/Checkbox';
import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';

import SearchHistory from './SearchHistory';

import { getRssFeedUrl } from '../../utils/rssUtils';
import { searchSubstack } from '../../utils/substackUtils';

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
            console.log('res', searchResult)

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

            console.log('Publication URL:', url);

            // Get RSS feed URL with error handling
            let feedUrl;
            try {
                feedUrl = await getRssFeedUrl(url);
            } catch (error) {
                console.error('Error getting RSS feed URL:', error);
                // Fallback to default Substack RSS feed pattern
                feedUrl = `${url}/feed`;
                console.log('Using default feed URL:', feedUrl);
            }

            // Convert search result to publication format
            const publication = {
                id: searchResult.handle || searchResult.subdomain || `pub-${Date.now()}`, // Temporary ID
                name: searchResult.name,
                title: searchResult.name,
                url: url,
                publisher: searchResult.publisher || searchResult.handle || 'Unknown Author',
                feed_url: feedUrl,
                handle: searchResult.handle || searchResult.subdomain,
            };

            const isAlreadySelected = selectedPublications.some(p => p.id === publication.id);
            if (isAlreadySelected) {
                removePublication(publication.id);
            } else {
                addPublication(publication);

                // Create/find publication in database to get real UUID
                if (onPublicationAdded) {
                    try {
                        const pubResponse = await fetch('/api/publications-db?action=find-or-create', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                title: publication.name,
                                url: url,
                                rss_feed_url: feedUrl,
                                publisher: publication.publisher
                            })
                        });

                        if (pubResponse.ok) {
                            const pubData = await pubResponse.json();
                            console.log('Publication created/found in database:', pubData.publication);

                            // Update publication with database ID and trigger preview fetch
                            if (pubData.publication?.id) {
                                const oldId = publication.id;
                                publication.id = pubData.publication.id;

                                // Update the ID in selectedPublications context
                                updatePublicationId(oldId, pubData.publication.id);

                                onPublicationAdded(publication);
                            }
                        } else {
                            console.error('Failed to create publication in database');
                        }
                    } catch (dbErr) {
                        console.error('Error creating publication in database:', dbErr);
                    }
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
    return (
        <Modal
            open={isOpen}
            onClose={onClose}
            sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'center', pt: 10 }}
        >
            <Paper sx={{ width: 600, height: 500, borderRadius: 0, overflow: 'hidden', backgroundColor: 'var(--white)' }}>
                {/* Header */}
                <Box sx={{ p: 3, borderBottom: 1, borderColor: 'grey.100' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <TextField
                            fullWidth
                            variant="outlined"
                            placeholder="People, publications, or topics"
                            value={searchQuery}
                            onChange={(e) => onSearchQueryChange(e.target.value)}
                            autoFocus
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchIcon sx={{ color: 'grey.600' }} />
                                    </InputAdornment>
                                ),
                                sx: { fontSize: '1.125rem' }
                            }}
                            sx={{ '& .MuiOutlinedInput-root': { border: 'none', '& fieldset': { border: 'none' } } }}
                        />
                        <IconButton
                            onClick={onClose}
                            sx={{ color: 'grey.400' }}
                        >
                            <CloseIcon />
                        </IconButton>
                    </Box>
                </Box>

                {/* Content */}
                <Box sx={{ p: 3, height: 400, overflow: 'auto' }}>
                    {searchResults.length > 0 ? (
                        /* Search Results */
                        <List>
                            {searchResults.map((result, index) => (
                                <ListItem key={index} sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}>
                                    <ListItemAvatar>
                                        <Avatar sx={{
                                            backgroundColor: 'secondary.main',
                                            color: 'secondary.contrastText',
                                            fontWeight: 'medium'
                                        }}>
                                            {(result.name && result.name.length > 0) ? result.name.charAt(0).toUpperCase() : '?'}
                                        </Avatar>
                                    </ListItemAvatar>
                                    <ListItemText
                                        primary={result.name}
                                        secondary={`${result.type === 'user' ? `@${result.handle}` : result.subdomain}${result.subscribers ? ` • ${result.subscribers}` : ''}`}
                                    />
                                    <Checkbox
                                        checked={isPublicationSelected(result)}
                                        onChange={() => handlePublicationToggle(result)}
                                        sx={{ mr: 1 }}
                                    />
                                </ListItem>
                            ))}
                        </List>
                    ) : (
                        /* Default Content - Selected Publications and Search History */
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                            {/* Selected Publications */}
                            {selectedPublications.length > 0 && (
                                <Box>
                                    <Box sx={{ mb: 2 }}>
                                        <Box sx={{ fontSize: '0.875rem', fontWeight: 'medium', color: 'grey.600', mb: 1 }}>
                                            Your Selected Publications
                                        </Box>
                                    </Box>
                                    <List>
                                        {selectedPublications.slice(0, 5).map((publication, index) => (
                                            <ListItem key={publication.id || index} sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}>
                                                <ListItemAvatar>
                                                    <Avatar sx={{
                                                        backgroundColor: 'primary.main',
                                                        color: 'primary.contrastText',
                                                        fontWeight: 'medium'
                                                    }}>
                                                        {(publication.name || publication.title || '').charAt(0).toUpperCase() || '?'}
                                                    </Avatar>
                                                </ListItemAvatar>
                                                <ListItemText
                                                    primary={publication.name || publication.title}
                                                    secondary={publication.subscribers ? `${publication.subscribers}` : (publication.handle ? `@${publication.handle}` : publication.url)}
                                                />
                                                <Checkbox
                                                    checked={true}
                                                    onChange={() => removePublication(publication.id)}
                                                    sx={{ mr: 1 }}
                                                />
                                            </ListItem>
                                        ))}
                                    </List>
                                </Box>
                            )}

                            {/* Search History */}
                            <SearchHistory
                                searchHistory={searchHistory}
                                onSelectHistory={onSelectHistory}
                                onRemoveFromHistory={onRemoveFromHistory}
                            />
                        </Box>
                    )}
                </Box>
            </Paper>
        </Modal >
    );
}