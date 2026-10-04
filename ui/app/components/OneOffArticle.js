'use client'

import { useState } from 'react'
import {
  Box,
  Typography,
  TextField,
  Button,
  CircularProgress,
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  FormControlLabel,
  Checkbox,
  Link,
} from '@mui/material'
import ArticleIcon from '@mui/icons-material/Article'

export default function OneOffArticle() {
  const [url, setUrl] = useState('')
  const [layoutType, setLayoutType] = useState('essay')
  const [removeImages, setRemoveImages] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const handleConvert = async () => {
    setError(null)
    setResult(null)

    let cleanUrl = url.trim()
    if (!cleanUrl) {
      setError('Please enter an article URL')
      return
    }
    if (!cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) {
      cleanUrl = 'https://' + cleanUrl
    }

    setLoading(true)
    try {
      const response = await fetch('/api/oneoff/article', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: cleanUrl, layout_type: layoutType, remove_images: removeImages }),
      })

      const data = await response.json()

      if (!response.ok) {
        setError(data.error || 'Conversion failed')
        return
      }

      setResult(data)
    } catch (err) {
      setError('Network error — please try again')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box sx={{ p: 3, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <ArticleIcon />
        <Typography variant="h6">Convert a Single Article</Typography>
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Paste any article URL to convert it to a PDF — no publication setup required.
        Supports Substack, Ghost, Beehiiv, and most article pages.
      </Typography>

      <TextField
        fullWidth
        label="Article URL"
        placeholder="https://example.substack.com/p/article-title"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && !loading && handleConvert()}
        disabled={loading}
        sx={{ mb: 2 }}
      />

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Layout</InputLabel>
          <Select
            value={layoutType}
            label="Layout"
            onChange={(e) => setLayoutType(e.target.value)}
            disabled={loading}
          >
            <MenuItem value="essay">Essay</MenuItem>
            <MenuItem value="newspaper">Newspaper</MenuItem>
          </Select>
        </FormControl>

        <FormControlLabel
          control={
            <Checkbox
              checked={removeImages}
              onChange={(e) => setRemoveImages(e.target.checked)}
              disabled={loading}
            />
          }
          label="Remove images"
        />
      </Box>

      <Button
        variant="contained"
        onClick={handleConvert}
        disabled={loading || !url.trim()}
        startIcon={loading ? <CircularProgress size={18} /> : null}
      >
        {loading ? 'Converting…' : 'Convert to PDF'}
      </Button>

      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}

      {result && (
        <Alert severity="success" sx={{ mt: 2 }}>
          PDF ready!{' '}
          <Link href={result.pdf_url} target="_blank" rel="noopener">
            Download PDF
          </Link>
          {result.platform_detected && result.platform_detected !== 'generic' && (
            <Typography variant="caption" display="block">
              Detected platform: {result.platform_detected}
            </Typography>
          )}
        </Alert>
      )}
    </Box>
  )
}
