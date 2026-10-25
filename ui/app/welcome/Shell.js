'use client'

import Box from '@mui/material/Box'

// Client wrapper for the page's root element (the .lp scope in landing.css). It is an MUI Box
// on purpose: Providers' CssBaseline makes emotion inline a global <style> ahead of the first
// element on the server, and a plain <div> in that spot fails to hydrate against it.
export default function Shell({ className, children }) {
  return <Box className={className}>{children}</Box>
}
