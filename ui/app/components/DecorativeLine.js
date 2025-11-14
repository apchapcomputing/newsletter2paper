import Box from '@mui/material/Box';

export default function DecorativeLine({ sx, ...props }) {
    return (
        <Box
            sx={{
                width: '100%',
                height: '2px',
                backgroundColor: 'var(--black)',
                mb: 2,
                ...sx
            }}
            {...props}
        />
    );
}