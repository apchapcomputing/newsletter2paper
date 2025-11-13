// Newsletter Configuration Context
import { createContext, useContext, useState, useEffect } from "react";
import { useAuth } from './useAuth';
import { createClient } from '../lib/supabase';

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
    const [userIssues, setUserIssues] = useState([]);
    const [loading, setLoading] = useState(false);

    const { user, session } = useAuth();
    const supabase = createClient();

    // Load configuration when user authentication state changes
    useEffect(() => {
        const loadConfig = async () => {
            if (user && session) {
                // User is authenticated - load from Supabase
                try {
                    setLoading(true);

                    // Load user's issues
                    const { data: issues, error } = await supabase
                        .from('issues')
                        .select('*')
                        .order('updated_at', { ascending: false });

                    if (error) {
                        console.error('Error loading user issues:', error);
                    } else {
                        setUserIssues(issues || []);

                        // If there's a current issue, load its config
                        const currentIssue = issues?.find(issue => issue.id === currentIssueId);
                        if (currentIssue) {
                            setNewspaperTitle(currentIssue.title || '');
                            setOutputMode(currentIssue.format || 'newspaper');
                        }
                    }
                } catch (error) {
                    console.error('Error loading configuration from Supabase:', error);
                } finally {
                    setLoading(false);
                }
            } else {
                // User not authenticated - load from localStorage
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
                }
                setUserIssues([]);
            }
            setIsLoaded(true);
        };

        loadConfig();
    }, [user, session]); // Reload when auth state changes

    // Save to localStorage for anonymous users
    useEffect(() => {
        if (isLoaded && !user) {
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
    }, [newspaperTitle, outputMode, currentIssueId, isLoaded, user]);

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

    // Save issue to Supabase (for authenticated users)
    const saveIssueToSupabase = async (issueData) => {
        if (!user || !session) {
            throw new Error('User must be authenticated to save issues');
        }

        try {
            const issuePayload = {
                user_id: user.id,
                title: issueData.title || null,
                format: issueData.format || 'newspaper',
                frequency: issueData.frequency || 'weekly',
                target_email: user.email,
                status: 'draft'
            };

            let result;
            if (currentIssueId) {
                // Update existing issue
                result = await supabase
                    .from('issues')
                    .update(issuePayload)
                    .eq('id', currentIssueId)
                    .eq('user_id', user.id) // Ensure user owns this issue
                    .select()
                    .single();
            } else {
                // Create new issue
                result = await supabase
                    .from('issues')
                    .insert(issuePayload)
                    .select()
                    .single();
            }

            if (result.error) {
                throw result.error;
            }

            const savedIssue = result.data;
            setCurrentIssueId(savedIssue.id);

            // Refresh user issues
            const { data: refreshedIssues } = await supabase
                .from('issues')
                .select('*')
                .order('updated_at', { ascending: false });

            setUserIssues(refreshedIssues || []);

            return savedIssue;
        } catch (error) {
            console.error('Error saving issue to Supabase:', error);
            throw error;
        }
    };

    // Load specific issue
    const loadIssue = async (issueId) => {
        if (!user || !session) return;

        try {
            const { data: issue, error } = await supabase
                .from('issues')
                .select('*')
                .eq('id', issueId)
                .eq('user_id', user.id)
                .single();

            if (error) {
                throw error;
            }

            setNewspaperTitle(issue.title || '');
            setOutputMode(issue.format || 'newspaper');
            setCurrentIssueId(issue.id);

            return issue;
        } catch (error) {
            console.error('Error loading issue:', error);
            throw error;
        }
    };

    return (
        <NewsletterConfigContext.Provider value={{
            // State
            newspaperTitle,
            outputMode,
            currentIssueId,
            isLoaded,
            userIssues,
            loading,

            // Actions
            updateTitle,
            updateOutputMode,
            updateIssueId,
            resetConfig,
            saveIssueToSupabase,
            loadIssue,

            // Auth-related state
            isAuthenticated: !!user
        }}>
            {children}
        </NewsletterConfigContext.Provider>
    );
};