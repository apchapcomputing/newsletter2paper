'use client'

import { useState, useEffect } from 'react';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Link from '@mui/material/Link';

import SearchModal from './components/SearchModal';
import AuthModal from './components/AuthModal';
import AuthButton from './components/AuthButton';
import ConfigureNewspaper from './components/ConfigureNewspaper';
import AddPublications from './components/AddPublications';
import ActionButtonsSection from './components/ActionButtonsSection';

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

    // Check if user is authenticated
    if (!user) {
      alert('Please sign in to save your newsletter issue');
      return;
    }

    setIsSaving(true);
    try {
      // Use Supabase to save the issue
      const savedIssue = await saveIssueToSupabase({
        title: newspaperTitle,
        format: outputMode,
        frequency: 'weekly'
      });

      console.log('Issue saved successfully to Supabase!', savedIssue);

      // TODO: Save selected publications to Supabase
      // For now, we'll continue with the existing API for publications
      // Later we can migrate this to work directly with Supabase

      // Step 2: Save selected publications (keeping existing logic for now)
      if (selectedPublications.length > 0) {
        // First, ensure all publications exist in the database
        const publicationIds = [];

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

        // Add publications to issue
        if (publicationIds.length > 0) {
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
            throw new Error('Failed to save publications to issue');
          }
        }
      }

    } catch (error) {
      console.error('Error saving issue:', error);
      alert(`Failed to save issue: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleGeneratePdf = async () => {
    if (!currentIssueId) {
      alert('Please save your issue first before generating a PDF');
      return;
    }

    if (isGeneratingPdf) return; // Prevent double clicks

    setIsGeneratingPdf(true);
    setPdfUrl(null);

    try {
      // Use authenticated API call to Python backend
      const data = await apiPost(`/pdf/generate/${currentIssueId}`, {
        layout_type: outputMode
      });

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
      alert(`Failed to generate PDF: ${error.message}`);
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const handlePublicationToggle = (publication) => {
    const isAlreadySelected = selectedPublications.some(p => p.id === publication.id);
    if (isAlreadySelected) {
      removePublication(publication.id);
    } else {
      addPublication(publication);
    }
  }

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
      <AuthButton />
      <main className="flex flex-col gap-[32px] items-center sm:items-start max-w-4xl w-full mx-auto px-8">
        {/* Header Section */}
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', textAlign: 'center', mb: 4, mt: 2 }}>
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
              color: 'black'
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
              opacity: 0.8
            }}
          >
            EST. 2025 • SUBSTACK RSS TO NEWSPAPER PDF • VOLUME 0
          </Typography>
        </Box>

        {/* Configure Your Newspaper Section */}
        <ConfigureNewspaper />

        <Box sx={{
          width: '100%',
          height: '2px',
          backgroundColor: 'black',
          mb: 2
        }} />

        {/* Reset Button */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <Button
            variant="outlined"
            onClick={handleClearAll}
            disabled={!newspaperTitle && selectedPublications.length === 0}
            sx={{
              textTransform: 'none',
              fontWeight: 500,
              color: '#d32f2f',
              borderColor: '#d32f2f',
              px: 3,
              py: 1.5,
              '&:hover': {
                borderColor: '#b71c1c',
                backgroundColor: 'rgba(211, 47, 47, 0.04)'
              },
              '&:disabled': {
                color: '#bdbdbd',
                borderColor: '#e0e0e0'
              }
            }}
          >
            Reset Newspaper Configuration
          </Button>
        </Box>

        {/* Add Publications Section */}
        <AddPublications onOpenSearch={() => setIsSearchModalOpen(true)} />

        <Box sx={{
          width: '100%',
          height: '2px',
          backgroundColor: 'black',
          mb: 3
        }} />

        {/* Authentication Status Alert */}
        {!user && (
          <Alert
            severity="info"
            sx={{
              width: '100%',
              mb: 3,
              borderRadius: 2,
              '& .MuiAlert-message': {
                fontSize: '0.9rem'
              }
            }}
          >
            You&apos;re browsing as a guest.{' '}
            <Link
              component="button"
              variant="body2"
              onClick={() => setIsAuthModalOpen(true)}
              sx={{
                textDecoration: 'underline',
                color: 'primary.main',
                cursor: 'pointer',
                fontWeight: 600,
                '&:hover': {
                  color: 'primary.dark'
                }
              }}
            >
              Sign in
            </Link>
            {' '}to save your newsletter configurations and access them later!
          </Alert>
        )}

        {/* Action Buttons Section */}
        <ActionButtonsSection
          isSaving={isSaving}
          isGeneratingPdf={isGeneratingPdf}
          pdfUrl={pdfUrl}
          onSaveIssue={handleSaveIssue}
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
      <footer className="flex gap-4 flex-wrap items-center justify-center py-8 border-t border-gray-200">
        <Box sx={{
          width: '100%',
          height: '2px',
          backgroundColor: 'black',
        }} />
        <Typography
          variant="body2"
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
      </footer>
    </div >
  );
}
