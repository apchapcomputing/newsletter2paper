'use client'

import { createTheme } from '@mui/material/styles';

const theme = createTheme({
    palette: {
        primary: {
            main: '#A44200', // Orange dark
            light: '#c5541b', // Orange light
            contrastText: 'var(--white)',
        },
        secondary: {
            main: '#355C7D', // Blue dark
            light: '#4A6274', // Blue light
            contrastText: 'var(--white)',
        },
        error: {
            main: '#9E2A2B', // Red dark
            light: '#B23A3A', // Red light
            contrastText: 'var(--white)',
        },
        success: {
            main: '#3F5F43', // Green dark
            light: '#4F6F52', // Green light
            contrastText: 'var(--white)',
        },
        warning: {
            main: '#c5541b', // Orange light (formerly secondary)
            light: '#D58936', // Orange lighter
            contrastText: '#2A2619',
        },
        background: {
            default: 'var(--white)', // White background
            paper: 'var(--white)', // White paper background
        },
        text: {
            primary: '#2A2619', // Black text
            secondary: '#504f4e', // Grey text
        },
        grey: {
            50: 'var(--white)',
            100: '#504f4e',
            200: '#504f4e',
            300: '#504f4e',
            400: '#504f4e',
            500: '#504f4e',
            600: '#2A2619',
            700: '#2A2619',
            800: '#2A2619',
            900: '#2A2619',
        },
    },
    typography: {
        fontFamily: [
            'var(--font-geist-sans)',
            'Arial',
            'Helvetica',
            'sans-serif',
        ].join(','),
    },
    shadows: [
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
        'none',
    ],
    shape: {
        borderRadius: 0,
    },
    components: {
        MuiButton: {
            styleOverrides: {
                root: {
                    textTransform: 'none',
                    fontWeight: 500,
                    borderRadius: 0,
                    boxShadow: 'none',
                    '&:hover': {
                        boxShadow: 'none',
                    },
                },
            },
        },
        MuiToggleButton: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                    '&.Mui-selected': {
                        backgroundColor: '#A44200', // Primary orange dark
                        color: 'var(--white)',
                        '&:hover': {
                            backgroundColor: '#c5541b', // Orange light
                        },
                    },
                },
            },
        },
        MuiPaper: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                    boxShadow: 'none',
                },
            },
        },
        MuiAvatar: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                },
            },
        },
        MuiTextField: {
            styleOverrides: {
                root: {
                    '& .MuiOutlinedInput-root': {
                        borderRadius: 0,
                    },
                },
            },
        },
        MuiCheckbox: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                },
            },
        },
        MuiIconButton: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                },
            },
        },
    },
});

export default theme;