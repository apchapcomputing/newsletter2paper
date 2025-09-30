'use client'

import { SelectedPublicationsProvider } from './useSelectedPublications';

export default function Providers({ children }) {
    return (
        <SelectedPublicationsProvider>
            {children}
        </SelectedPublicationsProvider>
    );
}