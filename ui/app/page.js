'use client'

import { useState, useEffect, useRef } from 'react';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import IconButton from '@mui/material/IconButton';
import DeleteIcon from '@mui/icons-material/Delete';

import SearchModal from './components/SearchModal';
import AuthModal from './components/AuthModal';
import AuthButton from './components/AuthButton';
import ConfigureNewspaper from './components/ConfigureNewspaper';
import AddPublications from './components/AddPublications';
import PrintStep from './components/PrintStep';
import Masthead from './components/Masthead';
import Stepper from './components/Stepper';
import StepWindow from './components/StepWindow';
import Footer from './components/Footer';

import { getRssFeedUrl } from '../utils/rssUtils';
import { searchSubstack } from '../utils/substackUtils';
import logger from '../utils/logger';

import { useSelectedPublications } from '../contexts/useSelectedPublications';
import { useNewsletterConfig } from '../contexts/useNewsletterConfig';
import { useAuth } from '../contexts/useAuth';
import { apiFetch } from '../lib/apiFetch';
import { track, captureError } from '../lib/analytics';
import { useArticlePreviews } from '../lib/useArticlePreviews';
import {
  STEPS,
  clampStep,
  stepFromHash,
  hashForStep,
  articleWindowError,
  articleWindowQuery,
  describeArticleWindow,
  toQueryString,
  sheetsFilled,
  isStepDone,
} from '../lib/createFlow';

export default function Home() {
  const { selectedPublications, addPublication, removePublication, clearAllPublications, isLoaded } = useSelectedPublications();
  const {
    newspaperTitle,
    outputMode,
    removeImages,
    frequency,
    articleWindow,
    dateFrom,
    dateTo,
    currentIssueId,
    isLoaded: configLoaded,
    updateTitle,
    updateOutputMode,
    updateIssueId,
    resetConfig,
    saveIssueToSupabase,
    saveGuestIssue,
    loadIssue,
    removeIssue,
    userIssues,
    isAuthenticated
  } = useNewsletterConfig();
  const { user } = useAuth();

  const [publications, setPublications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mounted, setMounted] = useState(false);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchHistory, setSearchHistory] = useState([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [printStatus, setPrintStatus] = useState('');
  const printAbort = useRef(null);
  const [step, setStep] = useState(0);
  const [reached, setReached] = useState(0);
  const previews = useArticlePreviews();
  const [isPopulatingPublications, setIsPopulatingPublications] = useState(false);
  const [selectAnchorEl, setSelectAnchorEl] = useState(null);
  const isSelectMenuOpen = Boolean(selectAnchorEl);
  const [autoSaveTimer, setAutoSaveTimer] = useState(null);
  const isLoadingPublications = useRef(false);
  const addPublicationsRef = useRef(null);

  // Mark as mounted after client-side hydration completes.
  // This prevents server/client HTML mismatches caused by contexts that read
  // from localStorage (isLoaded/configLoaded are false on the client's first
  // render but the server may have rendered with them as true).
  useEffect(() => setMounted(true), []);

  // The step lives in the URL hash (#add, #configure, #print): the browser's back button and
  // deep links work, and the data itself comes back from the config contexts after a reload.
  useEffect(() => {
    const syncStep = () => {
      const next = stepFromHash(window.location.hash);
      setStep(next);
      setReached(prev => Math.max(prev, next));
    };
    syncStep();
    window.addEventListener('hashchange', syncStep);
    return () => window.removeEventListener('hashchange', syncStep);
  }, []);

  const goToStep = (index) => {
    const next = clampStep(index);
    if (next !== step) window.location.hash = hashForStep(next);
  };

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
      logger.log('Auto-saving issue...');
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
        logger.log('Guest user - publications managed via localStorage');
        setIsPopulatingPublications(false);
        return;
      }

      if (!currentIssueId || !configLoaded) {
        logger.log('Waiting for issue ID or config...', { currentIssueId, configLoaded });
        setIsPopulatingPublications(false);
        return;
      }

      try {
        setIsPopulatingPublications(true);
        isLoadingPublications.current = true;
        logger.log(`🔄 Loading publications for issue: ${currentIssueId}`);
        const pubResponse = await apiFetch(`/api/issues/${currentIssueId}/publications`);

        if (pubResponse.ok) {
          const pubData = await pubResponse.json();
          logger.log(`📊 Received publications data:`, pubData);

          // Clear existing publications and add the loaded ones
          clearAllPublications();
          logger.log('🗑️  Cleared all publications');

          if (pubData.publications && pubData.publications.length > 0) {
            logger.log(`➕ Adding ${pubData.publications.length} publications from database`);
            for (const pub of pubData.publications) {
              addPublication({
                id: pub.id,
                name: pub.title,
                title: pub.title,
                url: pub.url,
                publisher: pub.publisher,
                feed_url: pub.rss_feed_url,
                handle: pub.publisher,
                remove_images: pub.remove_images || false
              });
            }
            logger.log(`✅ Loaded ${pubData.publications.length} publications from database`);
          } else {
            logger.log('ℹ️  No publications found for this issue');
          }
        } else {
          logger.error('❌ Failed to fetch publications:', pubResponse.status, pubResponse.statusText);
        }
      } catch (error) {
        logger.error('❌ Error loading publications for issue:', error);
      } finally {
        // Use setTimeout to ensure the flag is reset after state updates complete
        setTimeout(() => {
          isLoadingPublications.current = false;
          setIsPopulatingPublications(false);
          logger.log('✓ Publications loading complete');
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
        logger.log('Fetched publications:', data);

        // get rss url for each publication url and save to state
        const publicationsWithRss = await Promise.all(data.publications.map(async (p) => {
          const rssUrl = await getRssFeedUrl(p.url);
          return { ...p, feed_url: rssUrl };
        }));
        setPublications(publicationsWithRss);
      } catch (err) {
        logger.error('Error fetching publications:', err);
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
          frequency: frequency,
          remove_images: removeImages,
          custom_start_date: frequency === 'custom' ? dateFrom || null : null,
          custom_end_date: frequency === 'custom' ? dateTo || null : null,
        });

        logger.log('Issue saved successfully to Supabase!', savedIssue);
      } else {
        // Guest user - create temporary issue for PDF generation
        savedIssue = await saveGuestIssue({
          title: newspaperTitle || 'Guest Newspaper',
          format: outputMode,
          frequency: 'once',
          remove_images: removeImages,
          custom_start_date: null,
          custom_end_date: null,
        });

        logger.log('Guest issue created successfully!', savedIssue);
      }

      // Step 2: Save selected publications
      // Only sync publications to database if there are any selected
      if (selectedPublications.length > 0) {
        logger.log(`💾 Syncing ${selectedPublications.length} publications to issue ${savedIssue.id}`);

        const publicationsWithSettings = [];

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
          publicationsWithSettings.push({
            publication_id: pubData.publication.id,
            remove_images: publication.remove_images || false
          });
        }

        logger.log(`📋 Publications with settings to save:`, publicationsWithSettings);

        // Update publications for this issue (this will clear old ones and add new ones)
        const pubResponse = await apiFetch(`/api/issues/${savedIssue.id}/publications`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            publications: publicationsWithSettings
          })
        });

        if (!pubResponse.ok) {
          const errorText = await pubResponse.text();
          console.error('❌ Failed to save publications:', errorText);
          throw new Error('Failed to save publications to issue');
        }

        const result = await pubResponse.json();
        logger.log('✅ Publications saved successfully:', result);
      } else {
        logger.log('ℹ️  No publications to save - skipping publication sync');
      }

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
    setPrintStatus('');

    const startedAt = Date.now();
    const generateProps = {
      layout: outputMode,
      frequency,
      publication_count: selectedPublications.length,
      is_guest: !user,
    };
    let errorType = 'save';
    track('pdf_generate_clicked', generateProps);

    try {
      // IMPORTANT: Ensure any pending save completes before generating PDF
      // This prevents race conditions where the PDF is generated with stale data
      logger.log('🔄 Ensuring issue is saved before generating PDF...');

      // Clear any pending auto-save timer and save immediately
      if (autoSaveTimer) {
        clearTimeout(autoSaveTimer);
        setAutoSaveTimer(null);
      }

      // Wait for any in-progress save to complete
      while (isSaving) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }

      // Perform one final save to ensure everything is up-to-date
      await handleSaveIssue();

      // Give Supabase a moment to process the update (prevents race conditions)
      await new Promise(resolve => setTimeout(resolve, 300));

      logger.log('✅ Issue saved, now generating PDF...');

      // Build the PDF generation URL from the article window
      errorType = 'validation';
      const windowQuery = articleWindowQuery({ articleWindow, frequency, dateFrom, dateTo });
      if (!windowQuery) {
        throw new Error(articleWindowError({ articleWindow, dateFrom, dateTo }));
      }
      const pdfApiUrl = `/api/pdf/generate/${currentIssueId}?${toQueryString(windowQuery)}&layout_type=${outputMode}`;
      logger.log(`📅 Article window: ${JSON.stringify(windowQuery)}`);

      // Call Next.js API route, which proxies to Python backend
      errorType = 'network';
      const abort = new AbortController();
      printAbort.current = abort;
      const response = await apiFetch(pdfApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: abort.signal,
      });

      errorType = response.status >= 500 ? 'backend_5xx' : response.ok ? 'bad_response' : 'backend_4xx';
      const data = await response.json();

      if (data.success && data.pdf_url) {
        track('pdf_generated', { ...generateProps, duration_ms: Date.now() - startedAt });
        setPdfUrl(data.pdf_url);
        logger.log('PDF generated successfully:', data.pdf_url);

        // Optionally open the PDF in a new tab
        window.open(data.pdf_url, '_blank');
      } else {
        throw new Error(data.message || 'PDF generation failed');
      }

    } catch (error) {
      if (error?.name === 'AbortError') {
        // "Stop the presses": the reader cancelled, so this is neither a failure nor an event.
        setPrintStatus('Presses stopped. Nothing was printed.');
        return;
      }
      console.error('Error generating PDF:', error);
      const failure = { ...generateProps, error_type: errorType, duration_ms: Date.now() - startedAt };
      track('pdf_generate_failed', failure);
      if (errorType !== 'validation') captureError(error, failure);
      setPrintStatus(errorType === 'validation'
        ? error.message
        : 'Your paper could not be printed. Check your connection and try again.');
    } finally {
      printAbort.current = null;
      setIsGeneratingPdf(false);
    }
  };

  const handleStopPrinting = () => {
    printAbort.current?.abort();
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

  const handleDeleteIssue = async (event, issueId) => {
    // Prevent the menu item click from firing
    event.stopPropagation();

    try {
      const response = await apiFetch(`/api/issues/${issueId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete issue');
      }

      logger.log('Issue deleted successfully');

      // Remove the issue from the dropdown list
      removeIssue(issueId);

      // If the deleted issue was the currently loaded one, clear the form
      if (currentIssueId === issueId) {
        handleClearAll();
      }
    } catch (error) {
      console.error('Error deleting issue:', error);
      alert('Failed to delete issue. Please try again.');
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

  // Don't render the form until mounted and both contexts are loaded
  if (!mounted || !isLoaded || !configLoaded) {
    return (
      <div className="n2p-page" style={{ minHeight: '100vh' }}>
        <main className="n2p-wrap">
          <p className="n2p-deck" role="status" style={{ paddingTop: 'var(--space-12)' }}>
            Loading your newsletter configuration…
          </p>
        </main>
      </div>
    );
  }

  const now = new Date();
  const dateLabel = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const paperName = newspaperTitle.trim() || 'Your Paper';

  // "in the last week" / "from 2026-01-01 to 2026-01-05"
  const windowText = describeArticleWindow({ articleWindow, frequency, dateFrom, dateTo });
  const windowLabel = windowText.startsWith('the last') ? `in ${windowText}` : `from ${windowText}`;
  const previewStates = selectedPublications.map(pub => previews.previewFor(pub.id));
  const stillCounting = previewStates.some(state => state.status === 'loading');
  const articleCount = previewStates.reduce((sum, state) => sum + (state.articles?.length || 0), 0);
  const countNoun = (n, noun) => `${n} ${noun}${n === 1 ? '' : 's'}`;
  const summary = selectedPublications.length === 0
    ? 'No newsletters yet'
    : [countNoun(selectedPublications.length, 'newsletter'),
       stillCounting ? 'counting articles…' : `${countNoun(articleCount, 'article')} ${windowLabel}`].join(' · ');

  const flow = {
    publicationCount: selectedPublications.length,
    title: newspaperTitle,
    format: outputMode,
    articleWindow,
    dateFrom,
    dateTo,
    isGenerating: isGeneratingPdf,
    hasPdf: Boolean(pdfUrl),
    visitedConfigure: reached >= 1,
  };
  const sheets = STEPS.map((_, i) => sheetsFilled(i, flow));
  const done = STEPS.map((_, i) => isStepDone(i, step, reached, flow));

  // Configure can only move on once the article window is usable; the field shows why.
  const configureBlocked = step === 1 && Boolean(articleWindowError({ articleWindow, dateFrom, dateTo }));

  const handleNext = () => {
    if (configureBlocked) {
      document.getElementById(dateFrom ? 'date-to' : 'date-from')?.focus();
      return;
    }
    goToStep(step + 1);
  };

  return (
    <div className="n2p-page" style={{ minHeight: '100vh' }}>
      <div className="n2p-wrap">
        {/* Utility row: saving status, saved papers, new issue, account */}
        <div className="n2p-toolbar">
          <span className="n2p-toolbar__who" role="status">
            {isSaving ? 'Saving changes…' : (!user && (
              <>
                Browsing as a guest.{' '}
                <button type="button" className="n2p-link" onClick={() => setIsAuthModalOpen(true)}>Sign in</button>
                {' '}to save papers and email them to yourself.
              </>
            ))}
          </span>
          {/* Only offered once there is a saved paper to open */}
          {user && userIssues && userIssues.length > 0 && (
            <button
              type="button"
              className="n2p-link"
              id="select-issue-button"
              onClick={handleSelectMenuOpen}
              aria-haspopup="menu"
              aria-expanded={isSelectMenuOpen ? 'true' : undefined}
            >
              Open saved paper
            </button>
          )}
          <button
            type="button"
            className="n2p-link"
            onClick={handleClearAll}
            disabled={!newspaperTitle && selectedPublications.length === 0}
          >
            New issue
          </button>
          <AuthButton />
        </div>

        <Masthead />

        <main>
          <div className="n2p-stepper-wrap">
            <Stepper current={step} sheets={sheets} done={done} onSelect={goToStep} />
          </div>

          <div className="n2p-window-wrap">
            <StepWindow
              index={step}
              onBack={() => goToStep(step - 1)}
              onNext={handleNext}
              summary={summary}
              nextBlocked={configureBlocked}
              nextDescribedBy={configureBlocked ? 'date-error' : undefined}
            >
              {step === 0 && (
                <AddPublications
                  ref={addPublicationsRef}
                  onOpenSearch={() => setIsSearchModalOpen(true)}
                  onSaveIssue={handleSaveIssue}
                  isSaving={isSaving}
                  isPopulatingPublications={isPopulatingPublications}
                  previews={previews}
                  windowLabel={windowLabel}
                />
              )}
              {step === 1 && <ConfigureNewspaper />}
              {step === 2 && (
                <PrintStep
                  paperName={paperName}
                  dateLabel={dateLabel}
                  previewFor={previews.previewFor}
                  isSaving={isSaving}
                  isGeneratingPdf={isGeneratingPdf}
                  pdfUrl={pdfUrl}
                  printStatus={printStatus}
                  onGeneratePdf={handleGeneratePdf}
                  onStopPrinting={handleStopPrinting}
                />
              )}
            </StepWindow>
          </div>
        </main>

        {/* Select Issue Dropdown Menu */}
        <Menu
          anchorEl={selectAnchorEl}
          open={isSelectMenuOpen}
          onClose={handleSelectMenuClose}
          slotProps={{
            list: { 'aria-labelledby': 'select-issue-button' },
            paper: { sx: { maxHeight: 300, width: '300px' } },
          }}
        >
          {userIssues && userIssues.length > 0 ? (
            userIssues.map((issue) => (
              <MenuItem
                key={issue.id}
                onClick={() => handleSelectIssue(issue)}
                sx={{ py: 1.5, px: 2, display: 'flex', alignItems: 'flex-start' }}
              >
                <div style={{ flexGrow: 1, minWidth: 0, marginRight: 8 }}>
                  <div style={{ fontWeight: 700 }}>{issue.title || 'Untitled Issue'}</div>
                  <div className="n2p-pub__dl">
                    {issue.frequency} · {issue.format} · updated {new Date(issue.updated_at || issue.created_at).toLocaleDateString()}
                  </div>
                </div>
                <IconButton
                  size="small"
                  aria-label={`Delete ${issue.title || 'Untitled Issue'}`}
                  onClick={(e) => handleDeleteIssue(e, issue.id)}
                  sx={{ flexShrink: 0, mt: -0.5, '&:hover': { color: 'var(--error)' } }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </MenuItem>
            ))
          ) : (
            <MenuItem disabled>No saved issues found</MenuItem>
          )}
        </Menu>

        {/* Footer */}
        <Footer />
      </div>

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
        onPublicationAdded={(pub) => addPublicationsRef.current?.handlePublicationAdded(pub)}
      />

      {/* Auth Modal */}
      <AuthModal
        open={isAuthModalOpen}
        trigger="guest_banner"
        onClose={() => setIsAuthModalOpen(false)}
      />
    </div>
  );
}
