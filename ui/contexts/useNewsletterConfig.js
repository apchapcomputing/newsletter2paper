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
    const [outputMode, setOutputMode] = useState('essay');
    const [removeImages, setRemoveImages] = useState(false);
    const [frequency, setFrequency] = useState('weekly');
    const [currentIssueId, setCurrentIssueId] = useState(null);
    const [isLoaded, setIsLoaded] = useState(false);
    const [userIssues, setUserIssues] = useState([]);
    const [loading, setLoading] = useState(false);

    const { user, session } = useAuth();
    const supabase = createClient();

    // Validate current issue ID exists in database
    const validateCurrentIssue = async () => {
        if (!currentIssueId) return true; // No issue ID to validate

        try {
            const { data, error } = await supabase
                .from('issues')
                .select('id')
                .eq('id', currentIssueId)
                .single();

            if (error || !data) {
                console.warn(`Current issue ID ${currentIssueId} not found in database, clearing it`);
                setCurrentIssueId(null);
                return false;
            }

            return true;
        } catch (error) {
            console.error('Error validating current issue:', error);
            setCurrentIssueId(null);
            return false;
        }
    };

    // Migrate guest issue to authenticated user issue
    const migrateGuestIssueToUser = async (issueId, userId) => {
        try {
            console.log('🔄 Migrating guest issue to authenticated user:', issueId, 'userId:', userId);

            // Check if this is a guest issue
            const { data: issue, error: fetchError } = await supabase
                .from('issues')
                .select('*')
                .eq('id', issueId)
                .single();

            if (fetchError) {
                console.error('❌ Error fetching issue:', fetchError);
                return false;
            }

            if (!issue) {
                console.warn('⚠️ Issue not found, skipping migration');
                return false;
            }

            console.log('📄 Issue found:', {
                id: issue.id,
                status: issue.status,
                frequency: issue.frequency,
                title: issue.title
            });

            // Only migrate if status is 'guest'
            if (issue.status !== 'guest') {
                console.log('ℹ️ Issue is not a guest issue (status:', issue.status + '), skipping migration');
                return false;
            }

            console.log('🔧 Updating issue status and frequency...');

            // Update issue: status='guest' -> 'draft', frequency='once' -> 'weekly'
            const { error: updateError } = await supabase
                .from('issues')
                .update({
                    status: 'draft',
                    frequency: 'weekly',
                    target_email: user.email // Also set the user's email
                })
                .eq('id', issueId);

            if (updateError) {
                console.error('❌ Error updating guest issue:', updateError);
                return false;
            }

            console.log('✅ Issue updated successfully');
            console.log('🔗 Creating user-issue association...');

            // Create user-issue association
            const { error: associationError } = await supabase
                .from('user_issues')
                .upsert({
                    user_id: userId,
                    issue_id: issueId
                }, {
                    onConflict: 'user_id,issue_id'
                });

            if (associationError) {
                console.error('❌ Error creating user-issue association:', associationError);
                return false;
            }

            console.log('✅ Successfully migrated guest issue to user!');
            return true;
        } catch (error) {
            console.error('❌ Error migrating guest issue:', error);
            return false;
        }
    };

    // Load configuration from localStorage and user issues when authentication state changes
    useEffect(() => {
        const loadConfig = async () => {
            // Always load current working config from localStorage first
            let localIssueId = null;
            try {
                const savedConfig = localStorage.getItem('newsletterConfig');
                if (savedConfig) {
                    const config = JSON.parse(savedConfig);
                    setNewspaperTitle(config.title || '');
                    setOutputMode(config.outputMode || 'newspaper');
                    setRemoveImages(config.removeImages || false);
                    setFrequency(config.frequency || 'weekly');
                    localIssueId = config.issueId || null;
                    setCurrentIssueId(localIssueId);
                    console.log('📋 Loaded from localStorage - issueId:', localIssueId);
                } else {
                    // No config in localStorage, clear state
                    console.log('ℹ️ No config found in localStorage');
                    setNewspaperTitle('');
                    setOutputMode('essay');
                    setRemoveImages(false);
                    setFrequency('weekly');
                    setCurrentIssueId(null);
                }
            } catch (error) {
                console.error('Error loading newsletter config from localStorage:', error);
            }

            // If user just logged out (user is null but we had data), clear everything
            if (!user && !session) {
                console.log('🧹 User logged out, clearing user issues');
                setUserIssues([]);
                setIsLoaded(true);
                return;
            }

            // If user is authenticated, also load their saved issues list
            if (user && session) {
                try {
                    setLoading(true);

                    // If there's a current issue ID (from localStorage), check if it's a guest issue and migrate it
                    if (localIssueId) {
                        console.log('🔍 Checking issue for migration:', localIssueId);
                        await migrateGuestIssueToUser(localIssueId, user.id);
                    } else {
                        console.log('ℹ️ No issue ID found in localStorage to migrate');
                    }

                    // Validate that the current issue ID still exists in the database
                    await validateCurrentIssue();

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
                // For guest users, still validate the current issue exists
                if (currentIssueId) {
                    await validateCurrentIssue();
                }
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
                    removeImages,
                    frequency,
                    issueId: currentIssueId
                };
                localStorage.setItem('newsletterConfig', JSON.stringify(config));
            } catch (error) {
                console.error('Error saving newsletter config to localStorage:', error);
            }
        }
    }, [newspaperTitle, outputMode, removeImages, frequency, currentIssueId, isLoaded]);

    const updateTitle = (title) => {
        setNewspaperTitle(title);
    };

    const updateOutputMode = (mode) => {
        setOutputMode(mode);
    };

    const updateRemoveImages = (value) => {
        setRemoveImages(value);
    };

    const updateFrequency = (value) => {
        setFrequency(value);
    };

    const updateIssueId = (issueId) => {
        setCurrentIssueId(issueId);
    };

    const resetConfig = () => {
        setNewspaperTitle('');
        setOutputMode('essay');
        setRemoveImages(false);
        setFrequency('weekly');
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
                status: 'draft',
                remove_images: issueData.remove_images || false
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
                    // If the issue doesn't exist anymore (deleted from database), clear the ID and create new
                    if (result.error.code === 'PGRST116' || result.error.message?.includes('No rows found')) {
                        console.warn(`Issue ${currentIssueId} not found in database, creating new issue`);
                        setCurrentIssueId(null); // Clear the invalid issue ID

                        // Create new issue instead
                        result = await supabase
                            .from('issues')
                            .insert(issuePayload)
                            .select()
                            .single();

                        if (result.error) {
                            throw result.error;
                        }

                        savedIssue = result.data;

                        // Create the user-issue association (upsert to handle duplicates)
                        const userIssueResult = await supabase
                            .from('user_issues')
                            .upsert({
                                user_id: user.id,
                                issue_id: savedIssue.id
                            }, {
                                onConflict: 'user_id,issue_id'
                            });

                        if (userIssueResult.error) {
                            console.error('Error creating user-issue association:', userIssueResult.error);
                        }
                    } else {
                        throw result.error;
                    }
                } else {
                    savedIssue = result.data;

                    // Ensure user-issue association exists for updated issue
                    const { data: existingAssociation } = await supabase
                        .from('user_issues')
                        .select('id')
                        .eq('user_id', user.id)
                        .eq('issue_id', savedIssue.id)
                        .single();

                    if (!existingAssociation) {
                        const userIssueResult = await supabase
                            .from('user_issues')
                            .upsert({
                                user_id: user.id,
                                issue_id: savedIssue.id
                            }, {
                                onConflict: 'user_id,issue_id'
                            });

                        if (userIssueResult.error) {
                            console.error('Error creating user-issue association:', userIssueResult.error);
                        }
                    }
                }
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

                // Create the user-issue association (upsert to handle duplicates)
                const userIssueResult = await supabase
                    .from('user_issues')
                    .upsert({
                        user_id: user.id,
                        issue_id: savedIssue.id
                    }, {
                        onConflict: 'user_id,issue_id'
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

    // Save temporary guest issue (for unauthenticated users)
    const saveGuestIssue = async (issueData) => {
        try {
            // Generate or get a guest session ID
            let guestSessionId = localStorage.getItem('guestSessionId');
            if (!guestSessionId) {
                guestSessionId = `guest_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
                localStorage.setItem('guestSessionId', guestSessionId);
            }

            const issuePayload = {
                title: issueData.title || 'Guest Newspaper',
                format: issueData.format || 'newspaper',
                frequency: 'once',
                status: 'guest',
                remove_images: issueData.remove_images || false
            };

            let savedIssue;
            let result;

            if (currentIssueId) {
                // Update existing guest issue
                result = await supabase
                    .from('issues')
                    .update(issuePayload)
                    .eq('id', currentIssueId)
                    .select()
                    .single();

                if (result.error) {
                    // If the issue doesn't exist anymore (deleted from database), clear the ID and create new
                    if (result.error.code === 'PGRST116' || result.error.message?.includes('No rows found')) {
                        console.warn(`Guest issue ${currentIssueId} not found in database, creating new guest issue`);
                        setCurrentIssueId(null); // Clear the invalid issue ID

                        // Create new guest issue instead
                        result = await supabase
                            .from('issues')
                            .insert(issuePayload)
                            .select()
                            .single();

                        if (result.error) {
                            throw result.error;
                        }

                        savedIssue = result.data;
                    } else {
                        throw result.error;
                    }
                } else {
                    savedIssue = result.data;
                }
            } else {
                // Create new guest issue
                result = await supabase
                    .from('issues')
                    .insert(issuePayload)
                    .select()
                    .single();

                if (result.error) {
                    throw result.error;
                }

                savedIssue = result.data;
            }

            setCurrentIssueId(savedIssue.id);
            return savedIssue;
        } catch (error) {
            console.error('Error saving guest issue to Supabase:', error);
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
            setOutputMode(issue.format || 'essay');
            setRemoveImages(issue.remove_images || false);
            setFrequency(issue.frequency || 'weekly');
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
            removeImages,
            frequency,
            currentIssueId,
            isLoaded,
            userIssues,
            loading,

            // Actions
            updateTitle,
            updateOutputMode,
            updateRemoveImages,
            updateFrequency,
            updateIssueId,
            resetConfig,
            saveIssueToSupabase,
            saveGuestIssue,
            loadIssue,
            validateCurrentIssue,

            // Auth-related state
            isAuthenticated: !!user
        }}>
            {children}
        </NewsletterConfigContext.Provider>
    );
};