'use client'

import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { SelectedPublicationsProvider } from './useSelectedPublications';
import theme from '../app/theme';

export default function Providers({ children }) {
    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <SelectedPublicationsProvider>
                {children}
            </SelectedPublicationsProvider>
        </ThemeProvider>
    );
}