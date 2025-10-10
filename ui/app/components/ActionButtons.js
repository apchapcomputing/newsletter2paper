import Button from '@mui/material/Button';
import Box from '@mui/material/Box';

export default function ActionButtons({ onGetRssFeed, onOpenSearch }) {
    return (
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button variant="contained" color="secondary">
                Now
            </Button>
            <Button variant="contained" color="secondary">
                Weekly
            </Button>
            <Button
                variant="contained"
                color="secondary"
                onClick={() => onGetRssFeed("http://kyla.substack.com")}
            >
                Get RSS Feed URL
            </Button>
            <Button
                variant="contained"
                color="primary"
                onClick={onOpenSearch}
            >
                Search Substack
            </Button>
        </Box>
    );
}