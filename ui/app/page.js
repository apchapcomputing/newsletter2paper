'use client'

import { useState, useEffect } from 'react';
import Image from "next/image";
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Modal from '@mui/material/Modal';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import ListItemAvatar from '@mui/material/ListItemAvatar';
import Avatar from '@mui/material/Avatar';
import Paper from '@mui/material/Paper';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import HistoryIcon from '@mui/icons-material/History';

export default function Home() {
  const [publications, setPublications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchHistory, setSearchHistory] = useState([]);

  // Sample featured publications (you can replace with real data)
  const featuredPublications = [
    { name: 'Supernu...', avatar: '🏠' },
    { name: 'Ashlyn ...', avatar: '👩' },
    { name: "Kyla's N...", avatar: '💡' },
    { name: 'Open W...', avatar: '📖' }
  ];

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
            name: result.user.publication_name,
            type: 'user',
            handle: result.user.handle,
            subscribers: result.user.subscriber_count_string
          };
        } else if (result.type === 'publication') {
          return {
            name: result.publication.name,
            type: 'publication',
            subdomain: result.publication.subdomain,
            subscribers: result.publication.subscriber_count_string
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
        <Typography variant="h2" component="h1" sx={{ fontWeight: 'bold', textAlign: { xs: 'center', sm: 'left' } }}>Your Newspaper</Typography>

        {/* Generate Buttons */}
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button variant="contained" sx={{ backgroundColor: '#fb923c' }}>Now</Button>
          <Button variant="contained" sx={{ backgroundColor: '#fb923c' }}>Weekly</Button>
          <Button variant="contained" sx={{ backgroundColor: '#fb923c' }} onClick={() => getRssFeedUrl("http://kyla.substack.com")}>Get RSS Feed URL</Button>
          <Button variant="contained" color="primary" onClick={() => setIsSearchModalOpen(true)}>Search Substack</Button>
        </Box>

        {/* List of Active Substacks to Print */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="h4" component="h2" sx={{ fontWeight: 'semibold' }}>Substacks to Print</Typography>
          {loading ? (
            <Typography>Loading publications...</Typography>
          ) : error ? (
            <Typography color="error">Error: {error}</Typography>
          ) : (
            <List>
              {publications.map((publication, index) => (
                <ListItem key={index}>
                  <ListItemText
                    primary={
                      <a
                        href={publication.feed_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: '#3b82f6', textDecoration: 'none' }}
                      >
                        {publication.title}
                      </a>
                    }
                    secondary={publication.publisher && `(${publication.publisher})`}
                  />
                </ListItem>
              ))}
            </List>
          )}
        </Box>
      </main>

      {/* Search Modal */}
      <Modal
        open={isSearchModalOpen}
        onClose={() => {
          setIsSearchModalOpen(false);
          setSearchQuery('');
          setSearchResults([]);
        }}
        sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'center', pt: 10 }}
      >
        <Paper sx={{ width: 600, height: 500, borderRadius: 4, overflow: 'hidden' }}>
          {/* Header */}
          <Box sx={{ p: 3, borderBottom: 1, borderColor: 'grey.100' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <TextField
                fullWidth
                variant="outlined"
                placeholder="People, publications, or topics"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon sx={{ color: 'grey.600' }} />
                    </InputAdornment>
                  ),
                  sx: { fontSize: '1.125rem' }
                }}
                sx={{ '& .MuiOutlinedInput-root': { border: 'none', '& fieldset': { border: 'none' } } }}
              />
              <IconButton
                onClick={() => {
                  setIsSearchModalOpen(false);
                  setSearchQuery('');
                  setSearchResults([]);
                }}
                sx={{ color: 'grey.400' }}
              >
                <CloseIcon />
              </IconButton>
            </Box>
          </Box>

          {/* Content */}
          <Box sx={{ p: 3, height: 400, overflow: 'auto' }}>
            {searchResults.length > 0 ? (
              /* Search Results */
              <List>
                {searchResults.map((publication, index) => (
                  <ListItem key={index} sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}>
                    <ListItemAvatar>
                      <Avatar sx={{
                        background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
                        fontWeight: 'medium'
                      }}>
                        {publication.name.charAt(0)}
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={publication.name}
                      secondary={`${publication.type === 'user' ? `@${publication.handle}` : publication.subdomain}${publication.subscribers ? ` • ${publication.subscribers}` : ''}`}
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              /* Default Content - Featured Publications and Search History */
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {/* Featured Publications */}
                <Box>
                  <Grid container spacing={2} sx={{ mb: 3 }}>
                    {featuredPublications.map((pub, index) => (
                      <Grid item xs={3} key={index}>
                        <Card sx={{ cursor: 'pointer', '&:hover': { opacity: 0.75 }, textAlign: 'center' }}>
                          <CardContent>
                            <Avatar sx={{
                              width: 48,
                              height: 48,
                              margin: '0 auto 8px auto',
                              background: 'linear-gradient(135deg, #fb923c 0%, #ec4899 100%)',
                              fontSize: '1.125rem'
                            }}>
                              {pub.avatar}
                            </Avatar>
                            <Typography variant="body2" sx={{ fontWeight: 'medium', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                              {pub.name}
                            </Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                </Box>

                {/* Trending Topics */}
                <Box>
                  <List disablePadding>
                    <ListItem sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}>
                      <ListItemAvatar>
                        <TrendingUpIcon sx={{ color: 'grey.400', transform: 'rotate(45deg)' }} />
                      </ListItemAvatar>
                      <ListItemText primary="Self-driving cars expand deployment" />
                    </ListItem>
                    <ListItem sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}>
                      <ListItemAvatar>
                        <TrendingUpIcon sx={{ color: 'grey.400', transform: 'rotate(45deg)' }} />
                      </ListItemAvatar>
                      <ListItemText primary="emergency Pentagon generals meeting" />
                    </ListItem>
                    <ListItem sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}>
                      <ListItemAvatar>
                        <TrendingUpIcon sx={{ color: 'grey.400', transform: 'rotate(45deg)' }} />
                      </ListItemAvatar>
                      <ListItemText primary="White Out origins Penn State" />
                    </ListItem>
                    <ListItem sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}>
                      <ListItemAvatar>
                        <TrendingUpIcon sx={{ color: 'grey.400', transform: 'rotate(45deg)' }} />
                      </ListItemAvatar>
                      <ListItemText primary="Bitcoin Core v30 upgrade announced" />
                    </ListItem>
                    <ListItem sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}>
                      <ListItemAvatar>
                        <TrendingUpIcon sx={{ color: 'grey.400', transform: 'rotate(45deg)' }} />
                      </ListItemAvatar>
                      <ListItemText primary="Culture codes across platforms" />
                    </ListItem>
                  </List>
                </Box>

                {/* Search History */}
                <Box>
                  <List disablePadding>
                    {searchHistory.map((term, index) => (
                      <ListItem
                        key={index}
                        sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'grey.50' } }}
                        onClick={() => {
                          setSearchQuery(term);
                          searchSubstack(term);
                        }}
                        secondaryAction={
                          <IconButton
                            edge="end"
                            size="small"
                            sx={{ opacity: 0, '.MuiListItem-root:hover &': { opacity: 1 } }}
                            onClick={(e) => {
                              e.stopPropagation();
                              removeFromSearchHistory(term);
                            }}
                          >
                            <CloseIcon fontSize="small" />
                          </IconButton>
                        }
                      >
                        <ListItemAvatar>
                          <HistoryIcon sx={{ color: 'grey.400' }} />
                        </ListItemAvatar>
                        <ListItemText primary={term} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              </Box>
            )}
          </Box>
        </Paper>
      </Modal>

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
