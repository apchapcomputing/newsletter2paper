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
    onRemoveFromHistory
}) {
    const { selectedPublications, addPublication, removePublication } = useSelectedPublications();

    const handlePublicationToggle = async (searchResult) => {
        // if result is type user, make a secondary search with the publication's name to get the publication domain
        console.log('res', searchResult)

        let url;
        if (searchResult.type === 'publication') {
            url = searchResult.domain;
        } else if (searchResult.type === 'user') {
            const results = await searchSubstack(searchResult.name);
            if (results.length > 0) {
                url = results[0].custom_domain || results[0].domain;
            }
        }
        // add 'https://' prefix if missing
        if (url && !url.startsWith('http')) {
            url = `https://${url}`;
        }
        console.log(url);
        const feedUrl = await getRssFeedUrl(url);

        // Convert search result to publication format
        const publication = {
            id: searchResult.handle || searchResult.subdomain, // Use handle or subdomain as unique ID
            title: searchResult.name,
            url: url,
            publisher: searchResult.publisher || searchResult.handle || 'Unknown Author',
            feed_url: feedUrl,
            handle: searchResult.handle,
            subscribers: searchResult.subscribers
        };

        const isAlreadySelected = selectedPublications.some(p => p.id === publication.id);
        if (isAlreadySelected) {
            removePublication(publication.id);
        } else {
            addPublication(publication);
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
            <Paper sx={{ width: 600, height: 500, borderRadius: 4, overflow: 'hidden' }}>
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
                                            background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
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
                                                        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
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
        </Modal>
    );
}