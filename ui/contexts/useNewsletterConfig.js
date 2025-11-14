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

    // Load configuration from localStorage and user issues when authentication state changes
    useEffect(() => {
        const loadConfig = async () => {
            // Always load current working config from localStorage first
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

            // If user is authenticated, also load their saved issues list
            if (user && session) {
                try {
                    setLoading(true);

                    // Load user's issues using junction table
                    const { data: userIssuesData, error } = await supabase
                        .from('user_issues')
                        .select(`
                            issue_id,
                            issues (*)
                        `)
                        .eq('user_id', user.id)
                        .order('created_at', { ascending: false });

                    if (error) {
                        console.error('Error loading user issues:', error);
                    } else {
                        const issues = userIssuesData?.map(ui => ui.issues) || [];
                        setUserIssues(issues);
                    }
                } catch (error) {
                    console.error('Error loading user issues from Supabase:', error);
                } finally {
                    setLoading(false);
                }
            } else {
                setUserIssues([]);
            }
            setIsLoaded(true);
        };

        loadConfig();
    }, [user, session]); // Reload when auth state changes

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

        // Clear localStorage
        try {
            localStorage.removeItem('newsletterConfig');
        } catch (error) {
            console.error('Error clearing newsletter config from localStorage:', error);
        }
    };

    // Save issue to Supabase (for authenticated users)
    const saveIssueToSupabase = async (issueData) => {
        if (!user || !session) {
            throw new Error('User must be authenticated to save issues');
        }

        try {
            const issuePayload = {
                title: issueData.title || null,
                format: issueData.format || 'newspaper',
                frequency: issueData.frequency || 'weekly',
                target_email: user.email,
                status: 'draft'
            };

            let savedIssue;
            let result;

            if (currentIssueId) {
                // Update existing issue
                result = await supabase
                    .from('issues')
                    .update(issuePayload)
                    .eq('id', currentIssueId)
                    .select()
                    .single();

                if (result.error) {
                    throw result.error;
                }

                savedIssue = result.data;
            } else {
                // Create new issue
                result = await supabase
                    .from('issues')
                    .insert(issuePayload)
                    .select()
                    .single();

                if (result.error) {
                    throw result.error;
                }

                savedIssue = result.data;

                // Create the user-issue association
                const userIssueResult = await supabase
                    .from('user_issues')
                    .insert({
                        user_id: user.id,
                        issue_id: savedIssue.id
                    });

                if (userIssueResult.error) {
                    console.error('Error creating user-issue association:', userIssueResult.error);
                    // Don't throw here - the issue was created successfully, association failed
                }
            }

            setCurrentIssueId(savedIssue.id);

            // Refresh user issues by getting all issues associated with this user
            const { data: refreshedIssues } = await supabase
                .from('user_issues')
                .select(`
                    issue_id,
                    issues (*)
                `)
                .eq('user_id', user.id)
                .order('created_at', { ascending: false });

            const userIssues = refreshedIssues?.map(ui => ui.issues) || [];
            setUserIssues(userIssues);

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
            // Check if user has access to this issue via user_issues junction table
            const { data: userIssue, error: accessError } = await supabase
                .from('user_issues')
                .select(`
                    issue_id,
                    issues (*)
                `)
                .eq('user_id', user.id)
                .eq('issue_id', issueId)
                .single();

            if (accessError) {
                throw accessError;
            }

            if (!userIssue) {
                throw new Error('Issue not found or access denied');
            }

            const issue = userIssue.issues;
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