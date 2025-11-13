'use client'

import { useState, useEffect } from 'react';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Alert from '@mui/material/Alert';
import Link from '@mui/material/Link';

import SearchModal from './components/SearchModal';
import AuthModal from './components/AuthModal';
import AuthButton from './components/AuthButton';

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

  const handleNewspaperTitleChange = (event) => {
    updateTitle(event.target.value);
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
      {/* Add Header */}
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
        <Box sx={{
          width: '100%',
          border: '2px solid black',
          p: 3,
          mb: 4
        }}>
          <Typography
            variant="h4"
            component="h2"
            sx={{
              textAlign: 'center',
              fontWeight: 600,
              mb: 1,
              fontSize: { xs: '1.5rem', sm: '2rem' }
            }}
          >
            Configure Your Newspaper
          </Typography>
          <Typography
            variant="body2"
            sx={{
              textAlign: 'center',
              fontStyle: 'italic',
              color: 'text.secondary',
              mb: 2
            }}
          >
            Configure the details for your newspaper
          </Typography>

          <Box sx={{
            width: '100%',
            height: '2px',
            backgroundColor: 'black',
            mb: 3
          }} />

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Title Input */}
            <Box>
              <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                TITLE
              </Typography>
              <TextField
                variant="outlined"
                fullWidth
                value={newspaperTitle}
                onChange={handleNewspaperTitleChange}
                placeholder="e.g., Morning News, Weekly Digest"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    backgroundColor: '#f5f5f5'
                  }
                }}
              />
            </Box>

            {/* Printing Schedule and Format Row */}
            <Box sx={{ display: 'flex', gap: 3, flexDirection: { xs: 'column', sm: 'row' } }}>
              {/* Printing Schedule */}
              <Box sx={{ flex: 1 }}>
                <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                  PRINTING SCHEDULE
                </Typography>
                <FormControl fullWidth>
                  <Select
                    value="weekly"
                    displayEmpty
                    sx={{
                      backgroundColor: '#f5f5f5'
                    }}
                  >
                    <MenuItem value="" disabled>
                      Select frequency
                    </MenuItem>
                    <MenuItem value="daily">Daily</MenuItem>
                    <MenuItem value="weekly">Weekly</MenuItem>
                    <MenuItem value="monthly">Monthly</MenuItem>
                  </Select>
                </FormControl>
              </Box>

              {/* Format */}
              <Box sx={{ flex: 1 }}>
                <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                  FORMAT
                </Typography>
                <FormControl fullWidth>
                  <Select
                    value={outputMode}
                    onChange={(e) => updateOutputMode(e.target.value)}
                    sx={{
                      backgroundColor: '#f5f5f5'
                    }}
                  >
                    <MenuItem value="" disabled>
                      Select format
                    </MenuItem>
                    <MenuItem value="newspaper">Newspaper</MenuItem>
                    <MenuItem value="essay">Essay</MenuItem>
                  </Select>
                </FormControl>
              </Box>
            </Box>
          </Box>
        </Box>

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
        <Box sx={{
          width: '100%',
          border: '2px solid black',
          p: 3,
          mb: 4
        }}>
          <Typography
            variant="h4"
            component="h2"
            sx={{
              textAlign: 'center',
              fontWeight: 600,
              mb: 1,
              fontSize: { xs: '1.5rem', sm: '2rem' }
            }}
          >
            Add Publications
          </Typography>
          <Typography
            variant="body2"
            sx={{
              textAlign: 'center',
              fontStyle: 'italic',
              color: 'text.secondary',
              mb: 2
            }}
          >
            Add Substack publications to print in your newspaper
          </Typography>

          <Box sx={{
            width: '100%',
            height: '2px',
            backgroundColor: 'black',
            mb: 3
          }} />

          {/* Add Publication Source Controls */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
            <Typography variant="body1" sx={{ fontWeight: 500 }}>
              ADD PUBLICATION SOURCE
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', sm: 'row' } }}>
              <Button
                variant="contained"
                onClick={() => setIsSearchModalOpen(true)}
                sx={{
                  flex: 1,
                  py: 1.5,
                  fontWeight: 'medium',
                  textTransform: 'none',
                  fontSize: '1rem',
                  backgroundColor: '#f5f5f5',
                  color: 'black',
                  border: '1px solid #ccc',
                  '&:hover': {
                    // backgroundColor: '#e0e0e0',
                    borderColor: 'black'
                  }
                }}
              >
                SEARCH
              </Button>
              <Button
                variant="contained"
                sx={{
                  flex: 1,
                  py: 1.5,
                  fontWeight: 'medium',
                  textTransform: 'none',
                  fontSize: '1rem',
                  backgroundColor: '#f5f5f5',
                  color: 'black',
                  border: '1px solid #ccc',
                  '&:hover': {
                    // backgroundColor: '#e0e0e0',
                    borderColor: 'black'
                  }
                }}
              >
                ADD VIA URL
              </Button>
            </Box>
          </Box>

          {/* Publications to Print */}
          <Box>
            <Typography variant="body1" sx={{ fontWeight: 500, mb: 2 }}>
              PUBLICATIONS TO PRINT
            </Typography>

            {/* Selected Publications List */}
            {selectedPublications.length > 0 ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {selectedPublications.map((publication, index) => (
                  <Box
                    key={publication.id || index}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      p: 2,
                      backgroundColor: '#f5f5f5',
                      border: '1px solid #ccc'
                    }}
                  >
                    <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                      <Typography variant="body1" sx={{ fontWeight: 500 }}>
                        {publication.name || publication.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {publication.subscribers ? `${publication.subscribers} • ${publication.handle || ''}` : publication.handle || publication.url}
                      </Typography>
                    </Box>
                    <Button
                      onClick={() => removePublication(publication.id || publication.name)}
                      sx={{
                        minWidth: 'auto',
                        p: 1,
                        color: 'text.secondary',
                        '&:hover': {
                          backgroundColor: 'primary'
                        }
                      }}
                    >
                      ×
                    </Button>
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                No publications selected yet. Use the search or add URL options above to add publications.
              </Typography>
            )}
          </Box>
        </Box>

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
        <Box sx={{
          display: 'flex',
          gap: 3,
          justifyContent: 'center',
          flexDirection: { xs: 'column', sm: 'row' },
          width: '100%',
          maxWidth: 600,
          mx: 'auto'
        }}>
          <Button
            variant="contained"
            onClick={handleSaveIssue}
            disabled={isSaving}
            sx={{
              flex: 1,
              py: 2,
              px: 4,
              fontWeight: 600,
              textTransform: 'none',
              fontSize: '1.1rem',
              backgroundColor: '#f5f5f5',
              color: 'black',
              border: '2px solid #ccc',
              '&:hover': {
                // backgroundColor: '#e0e0e0'
                borderColor: 'black'
              },
              '&:disabled': {
                backgroundColor: '#d0d0d0',
                color: '#666'
              }
            }}
          >
            {isSaving ? 'SAVING...' : 'SAVE NEWSPAPER'}
          </Button>

          <Button
            variant="contained"
            onClick={handleGeneratePdf}
            disabled={isGeneratingPdf || !currentIssueId}
            sx={{
              flex: 1,
              py: 2,
              px: 4,
              fontWeight: 600,
              textTransform: 'none',
              fontSize: '1.1rem',
              backgroundColor: '#f5f5f5',
              color: 'black',
              border: '2px solid #ccc',
              '&:hover': {
                // backgroundColor: '#e0e0e0'
                borderColor: 'black'
              },
              '&:disabled': {
                backgroundColor: '#d0d0d0',
                color: '#666'
              }
            }}
          >
            {isGeneratingPdf ? 'GENERATING...' : 'PRINT NEWSPAPER'}
          </Button>
        </Box>

        {/* Status Messages */}
        {!currentIssueId && selectedPublications.length > 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: 2 }}>
            💡 Save your newspaper first, then print your PDF
          </Typography>
        )}

        {currentIssueId && (
          <Typography variant="body2" color="success.main" sx={{ textAlign: 'center', mt: 2 }}>
            ✅ Newspaper configuration saved! Ready to print
          </Typography>
        )}

        {/* Show PDF URL if available */}
        {pdfUrl && (
          <Box sx={{ mt: 3, p: 3, backgroundColor: '#e8f5e8', border: '1px solid #4caf50', textAlign: 'center' }}>
            <Typography variant="body1" color="success.main" sx={{ mb: 2, fontWeight: 500 }}>
              ✅ PDF generated successfully!
            </Typography>
            <Button
              variant="outlined"
              onClick={() => window.open(pdfUrl, '_blank')}
              sx={{
                textTransform: 'none',
                fontWeight: 500,
                borderColor: 'success.main',
                color: 'success.main',
                '&:hover': {
                  backgroundColor: 'success.light'
                }
              }}
            >
              📄 Open PDF
            </Button>
          </Box>
        )}
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
    </div>
  );
}
