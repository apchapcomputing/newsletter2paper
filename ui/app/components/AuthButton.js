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
                width: '100%',
                borderBottom: '1px solid #e0e0e0',
                backgroundColor: 'white',
                py: 2
            }}>
                <Container maxWidth="lg">
                    <Box sx={{
                        display: 'flex',
                        justifyContent: 'flex-end',
                        alignItems: 'center',
                        minHeight: 48
                    }}>
                        <Typography variant="body2" color="text.secondary">
                            Loading...
                        </Typography>
                    </Box>
                </Container>
            </Box>
        )
    }

    return (
        <>
            <Box sx={{
                width: '100%',
                py: 2,
            }}>
                <Container maxWidth="lg">
                    <Box sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 2
                    }}>
                        {/* Logo/Brand Space - Empty for now */}
                        <Box />

                        {user ? (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Box sx={{
                                    display: { xs: 'none', sm: 'flex' },
                                    flexDirection: 'column',
                                    alignItems: 'flex-end',
                                }}>
                                    <Typography variant="body2" sx={{ fontWeight: 500, color: 'var(--black)' }}>
                                        {user.user_metadata?.full_name?.split(' ')[0] || user.email?.split('@')[0]}
                                    </Typography>
                                </Box>
                                <UserMenu />
                            </Box>
                        ) : (
                            <Button
                                variant="outlined"
                                startIcon={<LoginIcon />}
                                onClick={() => setAuthModalOpen(true)}
                                sx={{
                                    textTransform: 'none',
                                    fontWeight: 500,
                                    px: 3,
                                    py: 1.25,
                                    borderRadius: 2,
                                    borderColor: 'transparent',
                                    color: 'var(--black)',
                                    backgroundColor: 'transparent',
                                    '&:hover': {
                                        borderColor: 'var(--black)',
                                        backgroundColor: 'transparent',
                                    }
                                }}
                            >
                                Get Started
                            </Button>
                        )}
                    </Box>
                </Container>
            </Box>

            <AuthModal
                open={authModalOpen}
                onClose={() => setAuthModalOpen(false)}
            />
        </>
    )
}