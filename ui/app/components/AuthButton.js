'use client'

import { useState } from 'react'
import { Box, Button, Typography, Container, Paper } from '@mui/material'
import { Login as LoginIcon } from '@mui/icons-material'
import { useAuth } from '../../contexts/useAuth'
import AuthModal from './AuthModal'
import UserMenu from './UserMenu'

export default function AuthButton() {
    const { user, loading } = useAuth()
    const [authModalOpen, setAuthModalOpen] = useState(false)

    if (loading) {
        return (
            <Box sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                py: 2,
                px: 4
            }}>
                <Typography variant="body2" color="text.secondary">
                    Loading...
                </Typography>
            </Box>
        )
    }

    return (
        <>
            <Box sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                alignItems: 'center',
                py: 2,
                px: { xs: 2, sm: 4 },
                gap: 2
            }}>
                {user ? (
                    <>
                        <Typography
                            variant="body2"
                            sx={{
                                fontWeight: 500,
                                color: 'var(--black)',
                                display: { xs: 'none', sm: 'block' }
                            }}
                        >
                            {user.user_metadata?.full_name?.split(' ')[0] || user.email?.split('@')[0]}
                        </Typography>
                        <UserMenu />
                    </>
                ) : (
                    <Button
                        variant="outlined"
                        onClick={() => setAuthModalOpen(true)}
                        sx={{
                            textTransform: 'none',
                            fontWeight: 500,
                            px: { xs: 1.5, sm: 3 },
                            py: 1.25,
                            minWidth: { xs: 'auto', sm: 'auto' },
                            borderRadius: 2,
                            borderColor: 'transparent',
                            color: 'var(--black)',
                            backgroundColor: 'transparent',
                            '&:hover': {
                                borderColor: 'var(--black)',
                                backgroundColor: 'rgba(0, 0, 0, 0.04)'
                            },
                        }}
                    >
                        <LoginIcon sx={{ display: { xs: 'block', sm: 'none' } }} />
                        <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 1 }}>
                            <LoginIcon />
                            Get Started
                        </Box>
                    </Button>
                )}
            </Box>

            <AuthModal
                open={authModalOpen}
                onClose={() => setAuthModalOpen(false)}
            />
        </>
    )
}