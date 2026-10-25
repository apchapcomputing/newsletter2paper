import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import ListItemIcon from '@mui/material/ListItemIcon';
import IconButton from '@mui/material/IconButton';
import HistoryIcon from '@mui/icons-material/History';
import CloseIcon from '@mui/icons-material/Close';
import Box from '@mui/material/Box';

export default function SearchHistory({
    searchHistory,
    onSelectHistory,
    onRemoveFromHistory
}) {
    if (searchHistory.length === 0) return null;
    return (
        <Box component="section" aria-labelledby="search-history-heading">
            <Box component="h3" id="search-history-heading" className="n2p-label-sm" sx={{ m: 0, mb: 1, color: 'var(--secondary)' }}>
                Recent searches
            </Box>
            <List disablePadding>
                {searchHistory.map((term) => (
                    <ListItem
                        key={term}
                        disablePadding
                        // The remove button is always visible: hover-only controls are out of reach
                        // for keyboard and touch users.
                        secondaryAction={
                            <IconButton
                                edge="end"
                                size="small"
                                aria-label={`Remove ${term} from recent searches`}
                                onClick={() => onRemoveFromHistory(term)}
                            >
                                <CloseIcon fontSize="small" />
                            </IconButton>
                        }
                    >
                        <ListItemButton onClick={() => onSelectHistory(term)} sx={{ pr: 7, '&:hover': { bgcolor: 'var(--secondary-soft)' } }}>
                            <ListItemIcon sx={{ minWidth: 40, color: 'var(--ink-muted)' }}><HistoryIcon /></ListItemIcon>
                            <ListItemText primary={term} />
                        </ListItemButton>
                    </ListItem>
                ))}
            </List>
        </Box>
    );
}
