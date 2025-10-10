'use client'

import { createTheme } from '@mui/material/styles';

const theme = createTheme({
    palette: {
        primary: {
            main: '#A44200', // Primary color
            contrastText: '#F7F5E2', // White color for text on primary
        },
        secondary: {
            main: '#D58936', // Secondary color
            contrastText: '#2A2619', // Black color for text on secondary
        },
        background: {
            default: '#F7F5E2', // White background
            paper: '#F7F5E2', // White paper background
        },
        text: {
            primary: '#2A2619', // Black text
            secondary: '#504f4e', // Grey text
        },
        grey: {
            50: '#F7F5E2',
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
                        backgroundColor: '#A44200',
                        color: '#F7F5E2',
                        '&:hover': {
                            backgroundColor: '#D58936',
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