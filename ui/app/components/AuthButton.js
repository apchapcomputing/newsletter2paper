'use client'

import { useState } from 'react'
import { useAuth } from '../../contexts/useAuth'
import AuthModal from './AuthModal'

// Account controls for the utility row: name and sign-out for members. Guests sign in from the
// guest line beside it, so there is no second sign-in button.
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
                    <button type="button" className="n2p-link" onClick={() => signOut()}>Sign out</button>
                </>
            ) : null}

            <AuthModal
                open={authModalOpen}
                trigger="header"
                onClose={() => setAuthModalOpen(false)}
            />
        </>
    )
}
