import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Checkbox from '@mui/material/Checkbox';

export default function PublicationsList({
    publications,
    loading,
    error,
    selectedPublications,
    onTogglePublication
}) {
    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography variant="h4" component="h2" sx={{ fontWeight: 'semibold' }}>
                Substacks to Print
            </Typography>
            {loading ? (
                <Typography>Loading publications...</Typography>
            ) : error ? (
                <Typography color="error">Error: {error}</Typography>
            ) : (
                <List>
                    {publications.map((publication, index) => (
                        <ListItem key={index}>
                            <Checkbox
                                checked={selectedPublications.some(p => p.id === publication.id)}
                                onChange={() => onTogglePublication(publication)}
                                sx={{ mr: 1 }}
                            />
                            <ListItemText
                                primary={
                                    <a
                                        href={publication.feed_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{ color: 'var(--primary)', textDecoration: 'none' }}
                                    >
                                        {publication.title}
                                    </a>
                                }
                                secondary={publication.publisher && `(${publication.publisher})`}
                            />
                        </ListItem>
                    ))}
                </List>
            )}
        </Box>
    );
}