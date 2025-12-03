// create context
import { createContext, useContext, useState, useEffect } from "react";
import { useAuth } from './useAuth';

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

    // Clear publications when user logs out
    useEffect(() => {
        if (!user && !session && isLoaded) {
            console.log('🧹 User logged out, clearing selected publications');
            setSelectedPublications([]);
        }
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
            return [...prev, publication];
        });
    };

    const removePublication = (publicationId) => {
        setSelectedPublications((prev) => prev.filter((p) => p.id !== publicationId));
    };

    const clearAllPublications = () => {
        setSelectedPublications([]);
    };

    return (
        <SelectedPublicationsContext.Provider value={{
            selectedPublications,
            addPublication,
            removePublication,
            clearAllPublications,
            isLoaded
        }}>
            {children}
        </SelectedPublicationsContext.Provider>
    );
}