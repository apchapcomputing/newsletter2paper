'use client'

import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { SelectedPublicationsProvider } from './useSelectedPublications';
import { NewsletterConfigProvider } from './useNewsletterConfig';
import { AuthProvider } from './useAuth';
import theme from '../app/theme';

export default function Providers({ children }) {
    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <AuthProvider>
                <SelectedPublicationsProvider>
                    <NewsletterConfigProvider>
                        {children}
                    </NewsletterConfigProvider>
                </SelectedPublicationsProvider>
            </AuthProvider>
        </ThemeProvider>
    );
}