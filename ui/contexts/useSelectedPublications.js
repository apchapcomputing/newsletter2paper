// create context
import { createContext, useContext, useState, useEffect, useRef } from "react";
import { useAuth } from './useAuth';
import logger from '../utils/logger';

const SelectedPublicationsContext = createContext();

// Custom hook to use the context
export const useSelectedPublications = () => {
    const context = useContext(SelectedPublicationsContext);
    if (!context) {
        throw new Error('useSelectedPublications must be used within a SelectedPublicationsProvider');
    }
    return context;
};

export const SelectedPublicationsProvider = ({ children }) => {
    const [selectedPublications, setSelectedPublications] = useState([]);
    const [isLoaded, setIsLoaded] = useState(false);
    const { user, session } = useAuth();

    // Load from localStorage on initial mount
    // For guest users: This is the primary data source
    // For logged-in users: This is temporary until database loads (via page.js effect)
    useEffect(() => {
        try {
            const saved = localStorage.getItem('selectedPublications');
            if (saved) {
                setSelectedPublications(JSON.parse(saved));
            }
        } catch (error) {
            console.error('Error loading selected publications from localStorage:', error);
        } finally {
            setIsLoaded(true);
        }
    }, []);

    // Clear publications when a signed-in user logs out. Guests (never signed in) keep their
    // selection: localStorage is its only copy, so it must survive reloads.
    const wasSignedIn = useRef(false);
    useEffect(() => {
        const signedIn = Boolean(user || session);
        if (wasSignedIn.current && !signedIn && isLoaded) {
            logger.log('🧹 User logged out, clearing selected publications');
            setSelectedPublications([]);
        }
        wasSignedIn.current = signedIn;
    }, [user, session, isLoaded]);

    // Save to localStorage whenever selectedPublications changes
    // For guest users: Primary persistence mechanism
    // For logged-in users: Cache only (database is source of truth)
    useEffect(() => {
        if (isLoaded) {
            try {
                localStorage.setItem('selectedPublications', JSON.stringify(selectedPublications));
            } catch (error) {
                console.error('Error saving selected publications to localStorage:', error);
            }
        }
    }, [selectedPublications, isLoaded]);

    const addPublication = (publication) => {
        setSelectedPublications((prev) => {
            if (prev.find((p) => p.id === publication.id)) {
                return prev; // already selected
            }
            // Ensure each publication has a remove_images property
            return [...prev, { ...publication, remove_images: publication.remove_images || false }];
        });
    };

    const removePublication = (publicationId) => {
        setSelectedPublications((prev) => prev.filter((p) => p.id !== publicationId));
    };

    const updatePublicationId = (oldId, newId) => {
        setSelectedPublications((prev) =>
            prev.map((p) =>
                p.id === oldId
                    ? { ...p, id: newId }
                    : p
            )
        );
    };

    const toggleRemoveImages = (publicationId) => {
        setSelectedPublications((prev) =>
            prev.map((p) =>
                p.id === publicationId
                    ? { ...p, remove_images: !p.remove_images }
                    : p
            )
        );
    };

    const clearAllPublications = () => {
        setSelectedPublications([]);
    };

    return (
        <SelectedPublicationsContext.Provider value={{
            selectedPublications,
            addPublication,
            removePublication, updatePublicationId, toggleRemoveImages,
            clearAllPublications,
            isLoaded
        }}>
            {children}
        </SelectedPublicationsContext.Provider>
    );
}