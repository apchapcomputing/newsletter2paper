'use client'

import { useState, useEffect } from 'react';
import Image from "next/image";
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Tooltip from '@mui/material/Tooltip';

import ActionButtons from './components/ActionButtons';
import PublicationsList from './components/PublicationsList';
import SelectedPublications from './components/SelectedPublications';
import SearchModal from './components/SearchModal';

import { getRssFeedUrl } from '../utils/rssUtils';
import { searchSubstack } from '../utils/substackUtils';

import { useSelectedPublications } from '../contexts/useSelectedPublications';
import { useNewsletterConfig } from '../contexts/useNewsletterConfig';

export default function Home() {
  const { selectedPublications, addPublication, removePublication, isLoaded } = useSelectedPublications();
  const {
    newspaperTitle,
    outputMode,
    currentIssueId,
    isLoaded: configLoaded,
    updateTitle,
    updateOutputMode,
    updateIssueId
  } = useNewsletterConfig();

  const [publications, setPublications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
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

    setIsSaving(true);
    try {
      // Step 1: Create or update issue
      let issueId = currentIssueId;

      if (!issueId) {
        // Create new issue
        const issueResponse = await fetch('/api/issues', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            title: newspaperTitle || null,
            format: outputMode,
            frequency: 'weekly'
            // TODO: set user login email as default target email
          })
        });

        if (!issueResponse.ok) {
          throw new Error('Failed to create issue');
        }

        const issueData = await issueResponse.json();
        issueId = issueData.issue.id;
        updateIssueId(issueId);
      } else {
        // Update existing issue
        const issueResponse = await fetch(`/api/issues?id=${issueId}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            title: newspaperTitle || null,
            format: outputMode
          })
        });

        if (!issueResponse.ok) {
          throw new Error('Failed to update issue');
        }
      }

      // Step 2: Save selected publications
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
          const pubResponse = await fetch(`/api/issues/${issueId}/publications`, {
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

      console.log('Issue saved successfully!');
      // Configuration is automatically persisted via the context
      // You could add a success notification here

    } catch (error) {
      console.error('Error saving issue:', error);
      // You could add an error notification here
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
      const response = await fetch(`/api/pdf/generate/${currentIssueId}?layout_type=${outputMode}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to generate PDF');
      }

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
      <div className="font-sans grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20" style={{ backgroundColor: '#F7F5E2' }}>
        <main className="flex flex-col gap-[32px] row-start-2 items-center sm:items-start">
          <Typography variant="h4" component="h1" sx={{ textAlign: 'center' }}>
            Loading your newsletter configuration...
          </Typography>
        </main>
      </div>
    );
  }

  return (
    <div className="font-sans grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20" style={{ backgroundColor: '#F7F5E2' }}>
      <main className="flex flex-col gap-[32px] row-start-2 items-center sm:items-start">
        <Typography
          variant="h2"
          component="h1"
          className="font-unifraktur font-bold"
          sx={{
            fontFamily: '"UnifrakturCook", cursive',
            fontWeight: 700,
            letterSpacing: '0.05em',
            textAlign: { xs: 'center', sm: 'left' }
          }}
        >
          Your {outputMode === 'newspaper' ? 'Newspaper' : 'Essays'}
        </Typography>
        <p>Substack RSS to Newspaper PDF</p>

        {/* Output Mode Toggle and Title Input */}
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: 2, alignItems: { xs: 'stretch', sm: 'center' }, width: '100%', maxWidth: 800 }}>
          <ToggleButtonGroup
            value={outputMode}
            exclusive
            onChange={handleOutputModeChange}
            aria-label="output mode"
            sx={{
              height: '56px', // Match TextField height
              '& .MuiToggleButton-root': {
                px: 3,
                fontWeight: 'medium',
                textTransform: 'none',
                fontSize: '1rem',
                height: '100%'
              }
            }}
          >
            <Tooltip title="Horizontal page with 3 columns" placement="top" enterDelay={1000}>
              <ToggleButton value="newspaper" aria-label="newspaper mode">
                📰 Newspaper
              </ToggleButton>
            </Tooltip>
            <Tooltip title="Classic APA styling. Vertical format." placement="top" enterDelay={1000}>
              <ToggleButton value="essay" aria-label="essay mode">
                📝 Essay
              </ToggleButton>
            </Tooltip>
          </ToggleButtonGroup>

          <TextField
            label={outputMode === 'newspaper' ? 'Newspaper Title' : 'Essay Title'}
            variant="outlined"
            value={newspaperTitle}
            onChange={handleNewspaperTitleChange}
            placeholder={outputMode === 'newspaper' ? 'Enter your newspaper name...' : 'Enter your essay title...'}
            sx={{ flexGrow: 1 }}
          />

          <Button
            variant="contained"
            color="primary"
            onClick={handleSaveIssue}
            disabled={isSaving}
            sx={{
              px: 3,
              py: 1.5,
              fontWeight: 'medium',
              textTransform: 'none',
              fontSize: '1rem',
              minWidth: 120
            }}
          >
            {isSaving ? '💾 Saving...' : currentIssueId ? '💾 Update' : '💾 Save'}
          </Button>
        </Box>

        {/* Action Buttons */}
        <ActionButtons
          onGetRssFeed={getRssFeedUrl}
          onOpenSearch={() => setIsSearchModalOpen(true)}
        />

        {/* Selected Publications */}
        <SelectedPublications />

        {/* PDF Generation Section */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'center' }}>
          {!currentIssueId && (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center' }}>
              💡 Save your issue first, then generate your PDF
            </Typography>
          )}

          {currentIssueId && (
            <Typography variant="body2" color="success.main" sx={{ textAlign: 'center' }}>
              ✅ Newsletter configuration saved! Ready to generate PDF
            </Typography>
          )}

          <Button
            variant="contained"
            color="primary"
            onClick={handleGeneratePdf}
            disabled={isGeneratingPdf || !currentIssueId}
            sx={{
              px: 3,
              py: 1.5,
              fontWeight: 'medium',
              textTransform: 'none',
              fontSize: '1rem',
              minWidth: 120
            }}>
            {isGeneratingPdf
              ? '📄 Generating...'
              : `Create ${outputMode.charAt(0).toUpperCase() + outputMode.slice(1)} Issue File`
            }
          </Button>

          {/* Show PDF URL if available */}
          {pdfUrl && (
            <Box sx={{ mt: 2, p: 2, backgroundColor: '#e8f5e8', borderRadius: 1 }}>
              <Typography variant="body2" color="success.main" sx={{ mb: 1 }}>
                ✅ PDF generated successfully!
              </Typography>
              <Button
                variant="outlined"
                size="small"
                onClick={() => window.open(pdfUrl, '_blank')}
                sx={{ textTransform: 'none' }}
              >
                📄 Open PDF
              </Button>
            </Box>
          )}
        </Box>
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

      {/* <footer className="row-start-3 flex gap-[24px] flex-wrap items-center justify-center">
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4 text-primary"
          href="https://nextjs.org/learn?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/file.svg"
            alt="File icon"
            width={16}
            height={16}
          />
          Learn
        </a>
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4 text-primary"
          href="https://vercel.com/templates?framework=next.js&utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/window.svg"
            alt="Window icon"
            width={16}
            height={16}
          />
          Examples
        </a>
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4 text-primary"
          href="https://nextjs.org?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/globe.svg"
            alt="Globe icon"
            width={16}
            height={16}
          />
          Go to nextjs.org →
        </a>
      </footer> */}
    </div>
  );
}
