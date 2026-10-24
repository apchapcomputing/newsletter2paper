'use client'

import { createTheme } from '@mui/material/styles';

// MUI carries the design system's tokens (see globals.css) to the controls that are not
// built from n2p-* classes: modals, menus, snackbars, form fields.
const ink = '#2a1820';
const border = `2px solid ${ink}`;
const focusRing = { outline: `3px solid ${ink}`, outlineOffset: '3px' };

const displayFont = 'var(--font-display)';
const typewriterFont = 'var(--font-typewriter)';

const theme = createTheme({
    palette: {
        primary: {
            main: '#6f98f2', // Cornflower: fills only
            dark: '#2f53b5', // Cornflower as text
            light: '#dde7fd',
            contrastText: ink,
        },
        secondary: {
            main: '#a44200', // Burnt orange: marks and links
            light: '#fff4e6',
            contrastText: '#fbf4ea',
        },
        error: {
            main: '#9e2a2b',
            contrastText: '#fbf4ea',
        },
        success: {
            main: '#3f5f43',
            contrastText: '#fbf4ea',
        },
        warning: {
            main: '#a44200',
            contrastText: '#fbf4ea',
        },
        background: {
            default: '#fbf4ea',
            paper: '#fffaf2',
        },
        text: {
            primary: ink,
            secondary: '#67505c',
        },
        divider: ink,
    },
    typography: {
        fontFamily: 'var(--font-sans)',
        fontSize: 17,
        h1: { fontFamily: displayFont, fontWeight: 700 },
        h2: { fontFamily: displayFont, fontWeight: 700 },
        h3: { fontFamily: displayFont, fontWeight: 700 },
        h4: { fontFamily: displayFont, fontWeight: 700 },
        h5: { fontFamily: displayFont, fontWeight: 700 },
        h6: { fontFamily: displayFont, fontWeight: 700 },
        button: { fontFamily: displayFont, fontWeight: 700, textTransform: 'uppercase' },
    },
    shadows: Array(25).fill('none'),
    shape: {
        borderRadius: 0,
    },
    components: {
        MuiCssBaseline: {
            styleOverrides: {
                body: { backgroundColor: '#fbf4ea', color: ink },
                '*:focus-visible': focusRing,
            },
        },
        MuiButtonBase: {
            defaultProps: { disableRipple: true },
            styleOverrides: {
                root: { '&.Mui-focusVisible': focusRing },
            },
        },
        MuiButton: {
            styleOverrides: {
                root: {
                    minHeight: 44,
                    borderRadius: 0,
                    boxShadow: 'none',
                    fontSize: 15,
                    lineHeight: '20px',
                    '&:hover': { boxShadow: 'none', transform: 'translate(-1px, -1px)' },
                    '&:active': { transform: 'translate(2px, 2px)' },
                    '@media (prefers-reduced-motion: reduce)': {
                        '&:hover': { transform: 'none' },
                    },
                },
                outlined: {
                    border,
                    color: ink,
                    backgroundColor: '#fffaf2',
                    '&:hover': { border, backgroundColor: '#fff4e6' },
                },
                contained: {
                    border,
                    boxShadow: 'inset 2px 2px 0 #ffffff99, inset -2px -2px 0 #2a182044',
                    '&:hover': { boxShadow: 'inset 2px 2px 0 #ffffff99, inset -2px -2px 0 #2a182044' },
                },
                text: {
                    color: '#a44200',
                    textDecorationThickness: '2px',
                },
            },
        },
        MuiToggleButton: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                    border,
                    '&.Mui-selected': {
                        backgroundColor: '#6f98f2',
                        color: ink,
                        '&:hover': { backgroundColor: '#6f98f2' },
                    },
                },
            },
        },
        MuiPaper: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                    boxShadow: 'none',
                    backgroundImage: 'none',
                },
            },
        },
        MuiDialog: {
            styleOverrides: {
                paper: {
                    border,
                    boxShadow: '4px 4px 0 #2a1820',
                },
            },
        },
        MuiDialogTitle: {
            styleOverrides: {
                root: { fontFamily: displayFont, fontWeight: 700 },
            },
        },
        MuiMenu: {
            styleOverrides: {
                paper: { border },
            },
        },
        MuiAvatar: {
            styleOverrides: {
                root: { borderRadius: 0 },
            },
        },
        MuiInputLabel: {
            styleOverrides: {
                root: {
                    fontFamily: typewriterFont,
                    fontWeight: 700,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    color: ink,
                    '&.Mui-focused': { color: ink },
                    '&.Mui-error': { color: '#9e2a2b' },
                },
            },
        },
        MuiOutlinedInput: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                    backgroundColor: '#fffaf2',
                    boxShadow: 'inset 3px 3px 0 #2a182044, inset -3px -3px 0 #ffffff99',
                    '& .MuiOutlinedInput-notchedOutline': { border, borderColor: ink },
                    '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: ink },
                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: ink, borderWidth: 2 },
                    '&.Mui-focused': focusRing,
                    '&.Mui-error .MuiOutlinedInput-notchedOutline': { borderColor: '#9e2a2b' },
                },
                input: { padding: '10px 14px', minHeight: 28 },
            },
        },
        MuiFormHelperText: {
            styleOverrides: {
                root: { fontSize: 14, lineHeight: '20px', marginLeft: 0 },
            },
        },
        MuiCheckbox: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                    color: ink,
                    '&.Mui-checked, &.MuiCheckbox-indeterminate': { color: '#2f53b5' },
                },
            },
        },
        MuiSwitch: {
            styleOverrides: {
                root: {
                    '& .MuiSwitch-track': { borderRadius: 0, border, opacity: 1, backgroundColor: '#f2e6d4' },
                    '& .MuiSwitch-thumb': { borderRadius: 0, border, backgroundColor: '#fffaf2', boxShadow: 'none' },
                    '& .Mui-checked + .MuiSwitch-track': { backgroundColor: '#6f98f2', opacity: 1 },
                },
            },
        },
        MuiIconButton: {
            styleOverrides: {
                root: {
                    borderRadius: 0,
                    color: ink,
                    border: '2px solid transparent',
                    '&:hover': { borderColor: ink, backgroundColor: 'transparent' },
                },
            },
        },
        MuiAlert: {
            styleOverrides: {
                root: { border, backgroundColor: '#fff4e6', color: ink },
                icon: { color: '#a44200' },
            },
        },
        MuiSnackbarContent: {
            styleOverrides: {
                root: { border, backgroundColor: '#fffaf2', color: ink, boxShadow: '4px 4px 0 #2a1820' },
            },
        },
        MuiLink: {
            defaultProps: { underline: 'always' },
            styleOverrides: {
                root: { color: '#a44200', fontWeight: 700, textDecorationThickness: '2px' },
            },
        },
        MuiTooltip: {
            styleOverrides: {
                tooltip: {
                    borderRadius: 0,
                    backgroundColor: ink,
                    color: '#fbf4ea',
                    fontFamily: 'var(--font-sans)',
                    fontSize: 14,
                },
            },
        },
    },
});

export default theme;
