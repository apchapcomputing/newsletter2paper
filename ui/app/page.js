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

import { useSelectedPublications } from '../contexts/useSelectedPublications';

export default function Home() {
  const { selectedPublications, addPublication, removePublication, isLoaded } = useSelectedPublications();

  const [publications, setPublications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchHistory, setSearchHistory] = useState([]);
  const [outputMode, setOutputMode] = useState('newspaper');
  const [newspaperTitle, setNewspaperTitle] = useState('');

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

  const getRssFeedUrl = async (url) => {
    try {
      const response = await fetch(`/api/rss/url?webpage_url=${encodeURIComponent(url)}`);
      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }
      const data = await response.json();
      return data.feed_url;
    } catch (error) {
      console.error("Failed to fetch RSS feed URL:", error);
    }
  }

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
      setOutputMode(newMode);
    }
  };

  const handleNewspaperTitleChange = (event) => {
    setNewspaperTitle(event.target.value);
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
    searchSubstack(term);
  }

  const searchSubstack = async (query) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      const response = await fetch(`/api/substack/search?query=${encodeURIComponent(query)}`);
      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }
      const data = await response.json();
      console.log('Substack search results:', data);

      // Parse results to extract publication names
      const publications = data.results?.map(result => {
        if (result.type === 'user') {
          return {
            name: result.user?.publication_name || 'Unknown Publication',
            type: 'user',
            handle: result.user?.handle,
            subscribers: result.user?.subscriber_count_string
          };
        } else if (result.type === 'publication') {
          return {
            name: result.publication?.name || 'Unknown Publication',
            type: 'publication',
            subdomain: result.publication?.subdomain,
            subscribers: result.publication?.subscriber_count_string
          };
        }
        return null;
      }).filter(Boolean) || [];

      setSearchResults(publications);

      // Add successful searches to history
      if (publications.length > 0) {
        addToSearchHistory(query);
      }
    } catch (error) {
      console.error("Failed to search Substack:", error);
      setSearchResults([]);
    }
  }

  // Debounce search to avoid too many API calls
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchQuery) {
        searchSubstack(searchQuery);
      }
    }, 500);
    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  return (
    <div className="font-sans grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20">
      <main className="flex flex-col gap-[32px] row-start-2 items-center sm:items-start">
        <Typography variant="h2" component="h1" sx={{ fontWeight: 'bold', textAlign: { xs: 'center', sm: 'left' } }}>
          Your {outputMode === 'newspaper' ? 'Newspaper' : 'Essay'} Issue
        </Typography>

        {/* Output Mode Toggle and Title Input */}
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: 3, alignItems: { xs: 'stretch', sm: 'center' }, width: '100%', maxWidth: 800 }}>
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
            sx={{
              px: 3,
              py: 1.5,
              fontWeight: 'medium',
              textTransform: 'none',
              fontSize: '1rem',
              minWidth: 120
            }}
          >
            💾 Save
          </Button>
        </Box>

        {/* Action Buttons */}
        <ActionButtons
          onGetRssFeed={getRssFeedUrl}
          onOpenSearch={() => setIsSearchModalOpen(true)}
        />

        {/* Selected Publications */}
        <SelectedPublications />
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

      <footer className="row-start-3 flex gap-[24px] flex-wrap items-center justify-center">
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
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
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
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
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
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
      </footer>
    </div>
  );
}
