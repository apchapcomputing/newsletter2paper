'use client'

import { useState } from 'react'
import LoginIcon from '@mui/icons-material/Login'
import LogoutIcon from '@mui/icons-material/Logout'
import { useAuth } from '../../contexts/useAuth'
import AuthModal from './AuthModal'

// Account controls for the utility row: "Get Started" for guests, name and sign-out for members.
export default function AuthButton() {
    const { user, loading, signOut } = useAuth()
    const [authModalOpen, setAuthModalOpen] = useState(false)

    if (loading) {
        return <span className="n2p-label" style={{ color: 'var(--ink-muted)' }}>Loading…</span>
    }

    return (
        <>
            {user ? (
                <>
                    <span className="n2p-label" style={{ color: 'var(--ink-muted)' }}>
                        {user.user_metadata?.full_name?.split(' ')[0] || user.email?.split('@')[0]}
                    </span>
                    <button type="button" className="n2p-btn n2p-btn--quiet" onClick={() => signOut()} aria-label="Sign out">
                        <LogoutIcon fontSize="small" aria-hidden="true" />
                    </button>
                </>
            ) : (
                <button type="button" className="n2p-btn" onClick={() => setAuthModalOpen(true)}>
                    <LoginIcon fontSize="small" aria-hidden="true" style={{ verticalAlign: '-4px', marginRight: 6 }} />
                    Get Started
                </button>
            )}

            <AuthModal
                open={authModalOpen}
                trigger="header"
                onClose={() => setAuthModalOpen(false)}
            />
        </>
    )
}
