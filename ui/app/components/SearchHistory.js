import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import ListItemAvatar from '@mui/material/ListItemAvatar';
import IconButton from '@mui/material/IconButton';
import HistoryIcon from '@mui/icons-material/History';
import CloseIcon from '@mui/icons-material/Close';
import Box from '@mui/material/Box';

export default function SearchHistory({
    searchHistory,
    onSelectHistory,
    onRemoveFromHistory
}) {
    return (
        <Box>
            <List disablePadding>
                {searchHistory.map((term, index) => (
                    <ListItem
                        key={index}
                        sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}
                        onClick={() => onSelectHistory(term)}
                        secondaryAction={
                            <IconButton
                                edge="end"
                                size="small"
                                sx={{ opacity: 0, '.MuiListItem-root:hover &': { opacity: 1 } }}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onRemoveFromHistory(term);
                                }}
                            >
                                <CloseIcon fontSize="small" />
                            </IconButton>
                        }
                    >
                        <ListItemAvatar>
                            <HistoryIcon sx={{ color: 'grey.400' }} />
                        </ListItemAvatar>
                        <ListItemText primary={term} />
                    </ListItem>
                ))}
            </List>
        </Box>
    );
}