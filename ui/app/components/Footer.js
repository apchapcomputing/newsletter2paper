import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import DecorativeLine from './DecorativeLine';

export default function Footer() {
    return (
        <footer className="flex gap-4 flex-wrap items-center justify-center py-8">
            <DecorativeLine sx={{ width: "95%", mb: 0, mx: 'auto' }} />
            <Box sx={{
                display: 'flex',
                flexDirection: { xs: 'column', sm: 'row' },
                gap: { xs: 1, sm: 2 },
                mt: 2,
                alignItems: 'center',
                px: { xs: 2, sm: 0 }
            }}>
                <Typography
                    variant="body2"
                    onClick={() => window.open('https://ashlynchapman.com', '_blank')}
                    sx={{
                        cursor: 'pointer',
                        color: '#504f4e',
                        fontSize: { xs: '0.75rem', sm: '0.875rem' },
                        textAlign: 'center',
                        '&:hover': {
                            color: 'secondary.main'
                        }
                    }}
                >
                    Made by Ashlyn Chapman
                </Typography>
                <Typography
                    variant="body2"
                    sx={{
                        color: '#504f4e',
                        display: { xs: 'none', sm: 'block' }
                    }}
                >
                    •
                </Typography>
                <Typography
                    variant="body2"
                    onClick={() => window.open('https://docs.google.com/forms/d/e/1FAIpQLScqMWrxF2SikunyJhR2VXkw2xfYAb950DT2bu0J8KtaTkcY7g/viewform?usp=sharing&ouid=112836351698515957727', '_blank')}
                    sx={{
                        cursor: 'pointer',
                        color: '#504f4e',
                        fontSize: { xs: '0.75rem', sm: '0.875rem' },
                        textAlign: 'center',
                        '&:hover': {
                            color: 'secondary.main'
                        }
                    }}
                >
                    Feature Request
                </Typography>
                {/* <Typography
                    variant="body2"
                    sx={{
                        color: '#504f4e',
                        display: { xs: 'none', sm: 'block' }
                    }}
                >
                    •
                </Typography>
                <Typography
                    variant="body2"
                    onClick={() => window.open('https://github.com/apchapcomputing/newsletter2paper', '_blank')}
                    sx={{
                        cursor: 'pointer',
                        color: '#504f4e',
                        fontSize: { xs: '0.75rem', sm: '0.875rem' },
                        textAlign: 'center',
                        '&:hover': {
                            color: 'secondary.main'
                        }
                    }}
                >
                    Source Code
                </Typography> */}
            </Box>
        </footer>
    );
}
