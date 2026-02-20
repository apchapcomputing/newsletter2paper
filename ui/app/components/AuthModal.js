'use client'

import { useState } from 'react'
import {
    Dialog,
    DialogTitle,
    DialogContent,
    Box,
    Typography,
    TextField,
    Button,
    IconButton,
    Divider,
    Alert,
    CircularProgress
} from '@mui/material'
import { Close as CloseIcon } from '@mui/icons-material'
import { useAuth } from '../../contexts/useAuth'

export default function AuthModal({ open, onClose }) {
    const [email, setEmail] = useState('')
    const [loading, setLoading] = useState(false)
    const [message, setMessage] = useState('')
    const [error, setError] = useState('')

    const { signInWithMagicLink, signInWithProvider } = useAuth()

    const handleMagicLinkSignIn = async (e) => {
        e.preventDefault()
        if (!email.trim()) {
            setError('Please enter your email address')
            return
        }

        setLoading(true)
        setError('')
        setMessage('')

        const result = await signInWithMagicLink(email)

        if (result.success) {
            setMessage('Check your email for a magic link to sign in!')
            setEmail('')
            // Don't close modal immediately, let user see the message
            setTimeout(() => {
                onClose()
                setMessage('')
            }, 3000)
        } else {
            setError(result.error || 'Failed to send magic link')
        }

        setLoading(false)
    }

    const handleOAuthSignIn = async (provider) => {
        setLoading(true)
        setError('')

        const result = await signInWithProvider(provider)

        if (!result.success) {
            setError(result.error || `Failed to sign in with ${provider}`)
        }

        setLoading(false)
        // OAuth will redirect, so we don't need to handle success here
    }

    const handleClose = () => {
        setEmail('')
        setError('')
        setMessage('')
        setLoading(false)
        onClose()
    }

    return (
        <Dialog
            open={open}
            onClose={handleClose}
            maxWidth="sm"
            fullWidth
            PaperProps={{
                sx: { borderRadius: 0, p: 1 }
            }}
        >
            <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1 }}>
                <Typography variant="h5" component="div" fontWeight={600}>
                    Get started
                </Typography>
                <IconButton onClick={handleClose} size="small">
                    <CloseIcon />
                </IconButton>
            </DialogTitle>

            <DialogContent sx={{ pt: 1 }}>
                {/* Error and success messages */}
                {error && (
                    <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                        {error}
                    </Alert>
                )}

                {message && (
                    <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMessage('')}>
                        {message}
                    </Alert>
                )}

                {/* Magic Link Form */}
                <Box component="form" onSubmit={handleMagicLinkSignIn} sx={{ mb: 3 }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Enter your email to get instant access with a magic link
                    </Typography>

                    <TextField
                        type="email"
                        label="Email address"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        fullWidth
                        required
                        disabled={loading}
                        sx={{ mb: 2 }}
                        placeholder="you@example.com"
                    />

                    <Button
                        type="submit"
                        fullWidth
                        variant="contained"
                        size="large"
                        disabled={loading}
                        sx={{
                            textTransform: 'none',
                            fontWeight: 600,
                            py: 1.5,
                            position: 'relative'
                        }}
                    >
                        {loading && <CircularProgress size={20} sx={{ mr: 1 }} />}
                        Send magic link
                    </Button>
                </Box>

                {/* Divider */}
                <Divider sx={{ my: 3 }}>
                    <Typography variant="body2" color="text.secondary">
                        or continue with
                    </Typography>
                </Divider>

                {/* OAuth Buttons */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>

                    {/* Google Login */}
                    <Button
                        fullWidth
                        variant="outlined"
                        size="large"
                        onClick={() => handleOAuthSignIn('google')}
                        disabled={loading}
                        sx={{
                            textTransform: 'none',
                            fontWeight: 500,
                            py: 1.5,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 2
                        }}
                    >
                        <svg width="20" height="20" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                        </svg>
                        Continue with Google
                    </Button>

                    {/* Facebook Login */}
                    {/* <Button
                        fullWidth
                        variant="outlined"
                        size="large"
                        onClick={() => handleOAuthSignIn('facebook')}
                        disabled={loading}
                        sx={{
                            textTransform: 'none',
                            fontWeight: 500,
                            py: 1.5,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 2,
                            borderColor: '#1877F2',
                            color: '#1877F2',
                            '&:hover': {
                                borderColor: '#1877F2',
                                backgroundColor: '#f0f8ff'
                            }
                        }}
                    >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                        </svg>
                        Continue with Facebook
                    </Button> */}

                </Box>
            </DialogContent>
        </Dialog>
    )
}