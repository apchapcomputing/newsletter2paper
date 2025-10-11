// Newsletter Configuration Context
import { createContext, useContext, useState, useEffect } from "react";

const NewsletterConfigContext = createContext();

// Custom hook to use the context
export const useNewsletterConfig = () => {
    const context = useContext(NewsletterConfigContext);
    if (!context) {
        throw new Error('useNewsletterConfig must be used within a NewsletterConfigProvider');
    }
    return context;
};

export const NewsletterConfigProvider = ({ children }) => {
    const [newspaperTitle, setNewspaperTitle] = useState('');
    const [outputMode, setOutputMode] = useState('newspaper');
    const [currentIssueId, setCurrentIssueId] = useState(null);
    const [isLoaded, setIsLoaded] = useState(false);

    // Load from localStorage on mount
    useEffect(() => {
        try {
            const savedConfig = localStorage.getItem('newsletterConfig');
            if (savedConfig) {
                const config = JSON.parse(savedConfig);
                setNewspaperTitle(config.title || '');
                setOutputMode(config.outputMode || 'newspaper');
                setCurrentIssueId(config.issueId || null);
            }
        } catch (error) {
            console.error('Error loading newsletter config from localStorage:', error);
        } finally {
            setIsLoaded(true);
        }
    }, []);

    // Save to localStorage whenever config changes
    useEffect(() => {
        if (isLoaded) {
            try {
                const config = {
                    title: newspaperTitle,
                    outputMode,
                    issueId: currentIssueId
                };
                localStorage.setItem('newsletterConfig', JSON.stringify(config));
            } catch (error) {
                console.error('Error saving newsletter config to localStorage:', error);
            }
        }
    }, [newspaperTitle, outputMode, currentIssueId, isLoaded]);

    const updateTitle = (title) => {
        setNewspaperTitle(title);
    };

    const updateOutputMode = (mode) => {
        setOutputMode(mode);
    };

    const updateIssueId = (issueId) => {
        setCurrentIssueId(issueId);
    };

    const resetConfig = () => {
        setNewspaperTitle('');
        setOutputMode('newspaper');
        setCurrentIssueId(null);
    };

    return (
        <NewsletterConfigContext.Provider value={{
            newspaperTitle,
            outputMode,
            currentIssueId,
            isLoaded,
            updateTitle,
            updateOutputMode,
            updateIssueId,
            resetConfig
        }}>
            {children}
        </NewsletterConfigContext.Provider>
    );
};