import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import Skeleton from '@mui/material/Skeleton';
import { useSelectedPublications } from '../../contexts/useSelectedPublications';

export default function SelectedPublications() {
    const { selectedPublications, removePublication, isLoaded } = useSelectedPublications();

    // Show loading skeleton while localStorage is being loaded
    if (!isLoaded) {
        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Skeleton variant="text" width={300} height={40} />
                <Box>
                    {[1, 2, 3].map((i) => (
                        <Skeleton key={i} variant="rectangular" height={60} sx={{ mb: 1, borderRadius: 1 }} />
                    ))}
                </Box>
            </Box>
        );
    }

    if (selectedPublications.length === 0) return null;

    const handleRemovePublication = (publicationId) => {
        removePublication(publicationId);
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography variant="h4" component="h2" sx={{ fontWeight: 'semibold' }}>
                newsletters for your newspaper ({selectedPublications.length})
            </Typography>
            <List>
                {selectedPublications.map((publication, index) => (
                    <ListItem
                        key={publication.id || index}
                        sx={{ bgcolor: 'green.50', mb: 1, borderRadius: 1 }}
                    >
                        <ListItemText
                            primary={publication.name || publication.title}
                            secondary={publication.subscribers ? `${publication.subscribers} subscribers` : publication.url}
                        />
                        <IconButton
                            onClick={() => handleRemovePublication(publication.id || publication.name)}
                            size="small"
                            sx={{
                                color: 'grey.500',
                                '&:hover': {
                                    color: 'grey.700',
                                    backgroundColor: 'grey.100'
                                }
                            }}
                        >
                            <CloseIcon fontSize="small" />
                        </IconButton>
                    </ListItem>
                ))}
            </List>
        </Box>
    );
}