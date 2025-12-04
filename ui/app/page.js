'use client'

import { useState, useEffect, useRef } from 'react';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Link from '@mui/material/Link';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';

import SearchModal from './components/SearchModal';
import AuthModal from './components/AuthModal';
import AuthButton from './components/AuthButton';
import ConfigureNewspaper from './components/ConfigureNewspaper';
import AddPublications from './components/AddPublications';
import ActionButtonsSection from './components/ActionButtonsSection';
import DecorativeLine from './components/DecorativeLine';

import { getRssFeedUrl } from '../utils/rssUtils';
import { searchSubstack } from '../utils/substackUtils';
import { apiPost } from '../utils/authApi';

import { useSelectedPublications } from '../contexts/useSelectedPublications';
import { useNewsletterConfig } from '../contexts/useNewsletterConfig';
import { useAuth } from '../contexts/useAuth';

export default function Home() {
  const { selectedPublications, addPublication, removePublication, clearAllPublications, isLoaded } = useSelectedPublications();
  const {
    newspaperTitle,
    outputMode,
    currentIssueId,
    isLoaded: configLoaded,
    updateTitle,
    updateOutputMode,
    updateIssueId,
    resetConfig,
    saveIssueToSupabase,
    saveGuestIssue,
    loadIssue,
    userIssues,
    isAuthenticated
  } = useNewsletterConfig();
  const { user } = useAuth();

  const [publications, setPublications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchHistory, setSearchHistory] = useState([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [selectAnchorEl, setSelectAnchorEl] = useState(null);
  const isSelectMenuOpen = Boolean(selectAnchorEl);
  const [autoSaveTimer, setAutoSaveTimer] = useState(null);
  const isLoadingPublications = useRef(false);

  // Auto-save effect - triggers when title, outputMode, or publications change
  useEffect(() => {
    // Don't auto-save until both contexts are loaded
    if (!isLoaded || !configLoaded) return;

    // Don't auto-save if we're currently loading publications from database
    if (isLoadingPublications.current) return;

    // Don't auto-save if there's no content to save
    if (!newspaperTitle && selectedPublications.length === 0) return;

    // Clear any existing timer
    if (autoSaveTimer) {
      clearTimeout(autoSaveTimer);
    }

    // Set a new timer to auto-save after 1 second of inactivity
    const timer = setTimeout(() => {
      console.log('Auto-saving issue...');
      handleSaveIssue();
    }, 1000);

    setAutoSaveTimer(timer);

    // Cleanup function
    return () => {
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [newspaperTitle, outputMode, selectedPublications, isLoaded, configLoaded]);

  // Load publications from database when issue ID changes (logged-in users only)
  // Guest users rely on localStorage for publications (handled by useSelectedPublications context)
  // Logged-in users load publications from issue_publications table in database
  useEffect(() => {
    const loadPublicationsForIssue = async () => {
      // Only load from database if user is logged in
      if (!user) {
        console.log('Guest user - publications managed via localStorage');
        return;
      }

      if (!currentIssueId || !configLoaded) {
        console.log('Waiting for issue ID or config...', { currentIssueId, configLoaded });
        return;
      }

      try {
        isLoadingPublications.current = true;
        console.log(`🔄 Loading publications for issue: ${currentIssueId}`);
        const pubResponse = await fetch(`/api/issues/${currentIssueId}/publications`);

        if (pubResponse.ok) {
          const pubData = await pubResponse.json();
          console.log(`📊 Received publications data:`, pubData);

          // Clear existing publications and add the loaded ones
          clearAllPublications();
          console.log('🗑️  Cleared all publications');

          if (pubData.publications && pubData.publications.length > 0) {
            console.log(`➕ Adding ${pubData.publications.length} publications from database`);
            for (const pub of pubData.publications) {
              addPublication({
                id: pub.id,
                name: pub.title,
                title: pub.title,
                url: pub.url,
                publisher: pub.publisher,
                feed_url: pub.rss_feed_url,
                handle: pub.publisher
              });
            }
            console.log(`✅ Loaded ${pubData.publications.length} publications from database`);
          } else {
            console.log('ℹ️  No publications found for this issue');
          }
        } else {
          console.error('❌ Failed to fetch publications:', pubResponse.status, pubResponse.statusText);
        }
      } catch (error) {
        console.error('❌ Error loading publications for issue:', error);
      } finally {
        // Use setTimeout to ensure the flag is reset after state updates complete
        setTimeout(() => {
          isLoadingPublications.current = false;
          console.log('✓ Publications loading complete');
        }, 100);
      }
    };

    loadPublicationsForIssue();
  }, [currentIssueId, configLoaded, user]);

  useEffect(() => {
    const fetchPublications = async () => {
      try {
        const response = await fetch('/api/publications');
        if (!response.ok) {
          throw new Error('Failed to fetch publications');
        }
        const data = await response.json();
        console.log('Fetched publications:', data);

        // get rss url for each publication url and save to state
        const publicationsWithRss = await Promise.all(data.publications.map(async (p) => {
          const rssUrl = await getRssFeedUrl(p.url);
          return { ...p, feed_url: rssUrl };
        }));
        setPublications(publicationsWithRss);
      } catch (err) {
        console.error('Error fetching publications:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPublications();
  }, []);

  const addToSearchHistory = (query) => {
    if (!query.trim()) return;

    setSearchHistory(prevHistory => {
      // Remove the query if it already exists (to avoid duplicates)
      const filteredHistory = prevHistory.filter(item => item.toLowerCase() !== query.toLowerCase());
      // Add the new query at the beginning and limit to 10 items
      return [query, ...filteredHistory].slice(0, 10);
    });
  }

  const removeFromSearchHistory = (queryToRemove) => {
    setSearchHistory(prevHistory =>
      prevHistory.filter(item => item !== queryToRemove)
    );
  }

  const handleOutputModeChange = (event, newMode) => {
    if (newMode !== null) {
      updateOutputMode(newMode);
    }
  };

  const handleSaveIssue = async () => {
    if (isSaving) return; // Prevent double saves

    setIsSaving(true);
    try {
      let savedIssue;

      if (user) {
        // Authenticated user - use full save functionality
        savedIssue = await saveIssueToSupabase({
          title: newspaperTitle,
          format: outputMode,
          frequency: 'weekly'
        });

        console.log('Issue saved successfully to Supabase!', savedIssue);
      } else {
        // Guest user - create temporary issue for PDF generation
        savedIssue = await saveGuestIssue({
          title: newspaperTitle || 'Guest Newspaper',
          format: outputMode,
          frequency: 'once'
        });

        console.log('Guest issue created successfully!', savedIssue);
      }

      // Step 2: Save selected publications
      // Always sync publications to database, even if empty (to handle deletions)
      console.log(`💾 Syncing ${selectedPublications.length} publications to issue ${savedIssue.id}`);

      const publicationIds = [];

      // First, ensure all publications exist in the database
      for (const publication of selectedPublications) {
        const pubResponse = await fetch('/api/publications-db?action=find-or-create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            title: publication.name || publication.title,
            url: publication.url,
            rss_feed_url: publication.feed_url || publication.url + '/feed',
            publisher: publication.publisher || publication.handle || 'Unknown'
          })
        });

        if (!pubResponse.ok) {
          console.error(`Failed to create/find publication: ${publication.name}`);
          continue;
        }

        const pubData = await pubResponse.json();
        publicationIds.push(pubData.publication.id);
      }

      console.log(`📋 Publication IDs to save:`, publicationIds);

      // Update publications for this issue (this will clear old ones and add new ones)
      const pubResponse = await fetch(`/api/issues/${savedIssue.id}/publications`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          publication_ids: publicationIds
        })
      });

      if (!pubResponse.ok) {
        const errorText = await pubResponse.text();
        console.error('❌ Failed to save publications:', errorText);
        throw new Error('Failed to save publications to issue');
      }

      const result = await pubResponse.json();
      console.log('✅ Publications saved successfully:', result);

    } catch (error) {
      console.error('Error saving issue:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleGeneratePdf = async () => {
    if (!currentIssueId) {
      return;
    }

    if (isGeneratingPdf) return; // Prevent double clicks

    setIsGeneratingPdf(true);
    setPdfUrl(null);

    try {
      // Call Next.js API route, which proxies to Python backend
      const response = await fetch(`/api/pdf/generate/${currentIssueId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (data.success && data.pdf_url) {
        setPdfUrl(data.pdf_url);
        console.log('PDF generated successfully:', data.pdf_url);

        // Optionally open the PDF in a new tab
        window.open(data.pdf_url, '_blank');
      } else {
        throw new Error(data.message || 'PDF generation failed');
      }

    } catch (error) {
      console.error('Error generating PDF:', error);
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const handleSearchModalClose = () => {
    setIsSearchModalOpen(false);
    setSearchQuery('');
    setSearchResults([]);
  }

  const handleSearchHistory = (term) => {
    setSearchQuery(term);
    performSearch(term);
  }

  const handleClearAll = () => {
    // Clear all form fields and selections
    resetConfig(); // Clears title, output mode, and current issue ID
    clearAllPublications(); // Clears all selected publications
    setPdfUrl(null); // Clear any existing PDF URL
  };

  const handleSelectMenuOpen = (event) => {
    setSelectAnchorEl(event.currentTarget);
  };

  const handleSelectMenuClose = () => {
    setSelectAnchorEl(null);
  };

  const handleSelectIssue = async (issue) => {
    handleSelectMenuClose();
    try {
      // Load the issue configuration (this will trigger the useEffect to load publications)
      await loadIssue(issue.id);
    } catch (error) {
      console.error('Error loading issue:', error);
    }
  };

  // Create a debounced search function
  const performSearch = async (query) => {
    const results = await searchSubstack(query);
    setSearchResults(results);

    // Add successful searches to history
    if (results.length > 0) {
      addToSearchHistory(query);
    }
  };

  // Debounce search to avoid too many API calls
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchQuery) {
        performSearch(searchQuery);
      }
    }, 500);
    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  // Don't render the form until both contexts are loaded
  if (!isLoaded || !configLoaded) {
    return (
      <div className="font-sans grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20" style={{ backgroundColor: '#ECECEC' }}>
        <main className="flex flex-col gap-[32px] row-start-2 items-center sm:items-start">
          <Typography variant="h4" component="h1" sx={{ textAlign: 'center' }}>
            Loading your newsletter configuration...
          </Typography>
        </main>
      </div>
    );
  }

  return (
    <div className="font-sans min-h-screen" style={{ backgroundColor: '#ECECEC' }}>
      {/* Header Section */}
      <AuthButton />
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', textAlign: 'center', mb: 4, mt: -4 }}>
        <Typography
          variant="h1"
          component="h1"
          className="font-unifraktur font-bold"
          sx={{
            fontFamily: '"UnifrakturCook", cursive',
            fontWeight: 700,
            letterSpacing: '0.05em',
            fontSize: { xs: '2.5rem', sm: '3.5rem' },
            lineHeight: 1.2,
            mb: 1,
            color: 'var(--black)'
          }}
        >
          The Newsletter Printing Press
        </Typography>
        <Typography
          variant="subtitle1"
          sx={{
            fontWeight: 400,
            letterSpacing: '0.1em',
            fontSize: { xs: '0.75rem', sm: '0.875rem' },
            color: 'text.secondary',
            opacity: 0.8,
            px: { xs: 3, sm: 0 },
            textAlign: 'center',
            lineHeight: 1.6
          }}
        >
          EST. 2025 • SUBSTACK RSS TO NEWSPAPER PDF • VOLUME 0
        </Typography>
      </Box>
      <DecorativeLine sx={{ width: "95%", mb: 4, mx: 'auto' }} />

      <main className="flex flex-col gap-[32px] items-center sm:items-start max-w-4xl w-full mx-auto px-8">

        {/* Auto-save Status Indicator */}
        <Box sx={{
          width: '100%',
          display: 'flex',
          justifyContent: 'center',
          mb: -2
        }}>
          <Typography
            variant="body2"
            sx={{
              color: isSaving ? '#A44200' : '#666',
              fontStyle: 'italic',
              fontSize: '0.85rem',
              opacity: 0.8
            }}
          >
            {isSaving ? '💾 Saving changes...' : ''}
          </Typography>
        </Box>

        {/* Authentication Status Alert */}
        {!user && (
          <Alert
            severity="info"
            sx={{
              width: '100%',
              borderRadius: 0,
              backgroundColor: '#ECECEC',
              border: '1px solid #c5541b',
              borderWidth: 2,
              color: '#291D18',
              '& .MuiAlert-icon': {
                color: '#A44200'
              },
              '& .MuiAlert-message': {
                fontSize: '0.9rem',
                color: '#291D18'
              }
            }}
          >
            You&apos;re browsing as a guest.{' '}
            <Link
              component="button"
              onClick={() => setIsAuthModalOpen(true)}
              sx={{
                textDecoration: 'none',
                color: '#A44200',
                cursor: 'pointer',
                fontWeight: 600,
                '&:hover': {
                  color: '#8B3500'
                }
              }}
            >
              Sign in
            </Link>
            {' '}to save your newsletter configurations, access them later, and email your issue PDFs to yourself!
          </Alert>
        )}

        {/* Select and Reset options */}
        <Box sx={{ display: 'flex', width: '100%', justifyContent: 'space-between', gap: 3 }}>
          <Button
            variant="outlined"
            onClick={handleSelectMenuOpen}
            disabled={!user || !userIssues || userIssues.length === 0}
            endIcon={<ArrowDropDownIcon />}
            sx={{
              textTransform: 'none',
              fontWeight: 500,
              fontSize: '1rem',
              color: 'var(--black)',
              borderColor: 'var(--black)',
              borderWidth: '2px',
              width: '100%',
              px: 4,
              py: 1.5,
              '&:hover': {
                borderColor: 'var(--black)',
                backgroundColor: 'rgba(0, 0, 0, 0.04)'
              },
              '&:disabled': {
                color: '#bdbdbd',
                borderColor: '#e0e0e0'
              }
            }}
          >
            SELECT
          </Button>
          <Button
            variant="outlined"
            onClick={handleClearAll}
            disabled={!newspaperTitle && selectedPublications.length === 0}
            sx={{
              textTransform: 'none',
              fontWeight: 500,
              fontSize: '1rem',
              color: 'var(--black)',
              borderColor: 'var(--black)',
              borderWidth: '2px',
              width: '100%',
              px: 4,
              py: 1.5,
              '&:hover': {
                borderColor: 'var(--black)',
                backgroundColor: 'rgba(0, 0, 0, 0.04)'
              },
              '&:disabled': {
                color: '#bdbdbd',
                borderColor: '#e0e0e0'
              }
            }}
          >
            RESET
          </Button>
        </Box>

        {/* Select Issue Dropdown Menu */}
        <Menu
          anchorEl={selectAnchorEl}
          open={isSelectMenuOpen}
          onClose={handleSelectMenuClose}
          MenuListProps={{
            'aria-labelledby': 'select-issue-button',
          }}
          PaperProps={{
            sx: {
              maxHeight: 300,
              width: '300px',
              border: '1px solid var(--black)'
            }
          }}
        >
          {userIssues && userIssues.length > 0 ? (
            userIssues.map((issue) => (
              <MenuItem
                key={issue.id}
                onClick={() => handleSelectIssue(issue)}
                sx={{
                  py: 1.5,
                  px: 2,
                  '&:hover': {
                    backgroundColor: 'rgba(0, 0, 0, 0.04)'
                  }
                }}
              >
                <Box>
                  <Typography variant="body1" sx={{ fontWeight: 500 }}>
                    {issue.title || 'Untitled Issue'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {issue.frequency} • {issue.format} • updated {new Date(issue.updated_at || issue.created_at).toLocaleDateString()}
                  </Typography>
                </Box>
              </MenuItem>
            ))
          ) : (
            <MenuItem disabled>
              <Typography variant="body2" color="text.secondary">
                No saved issues found
              </Typography>
            </MenuItem>
          )}
        </Menu>

        {/* Configure Your Newspaper Section */}
        <ConfigureNewspaper />

        <DecorativeLine />

        {/* Add Publications Section */}
        <AddPublications onOpenSearch={() => setIsSearchModalOpen(true)} />

        <DecorativeLine />

        {/* Action Buttons Section */}
        <ActionButtonsSection
          isSaving={isSaving}
          isGeneratingPdf={isGeneratingPdf}
          pdfUrl={pdfUrl}
          onGeneratePdf={handleGeneratePdf}
        />
      </main>

      {/* Search Modal */}
      <SearchModal
        isOpen={isSearchModalOpen}
        onClose={handleSearchModalClose}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        searchResults={searchResults}
        searchHistory={searchHistory}
        onSelectHistory={handleSearchHistory}
        onRemoveFromHistory={removeFromSearchHistory}
      />

      {/* Auth Modal */}
      <AuthModal
        open={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
      />

      {/* Footer */}
      <footer className="flex gap-4 flex-wrap items-center justify-center py-8">
        <DecorativeLine sx={{ width: "95%", mb: 0, mx: 'auto' }} />
        <Box sx={{
          display: 'flex',
          gap: 2,
          mt: 2
        }}>
          <Typography
            variant="body2"
            onClick={() => window.open('https://docs.google.com/forms/d/e/1FAIpQLScqMWrxF2SikunyJhR2VXkw2xfYAb950DT2bu0J8KtaTkcY7g/viewform?usp=sharing&ouid=112836351698515957727', '_blank')}
            sx={{
              textDecoration: 'underline',
              cursor: 'pointer',
              color: '#504f4e',
              '&:hover': {
                color: '#3b82f6'
              }
            }}
          >
            Feature Request
          </Typography>
          <Typography variant="body2" sx={{ color: '#504f4e' }}>
            •
          </Typography>
          <Typography
            variant="body2"
            onClick={() => window.open('https://github.com/apchapcomputing/newsletter2paper', '_blank')}
            sx={{
              textDecoration: 'underline',
              cursor: 'pointer',
              color: '#504f4e',
              '&:hover': {
                color: '#3b82f6'
              }
            }}
          >
            Source Code
          </Typography>
        </Box>
      </footer>
    </div >
  );
}
