'use client'

import { IconButton } from '@mui/material'
import { Logout as LogoutIcon } from '@mui/icons-material'
import { useAuth } from '../../contexts/useAuth'

export default function UserMenu() {
    const { signOut } = useAuth()

    const handleSignOut = async () => {
        await signOut()
    }

    return (
        <IconButton
            onClick={handleSignOut}
            size="medium"
            sx={{
                color: 'var(--black)',
                border: '1px solid transparent',
                '&:hover': {
                    borderColor: 'var(--black)',
                    backgroundColor: 'rgba(0, 0, 0, 0.04)'
                }
            }}
        >
            <LogoutIcon />
        </IconButton>
    )
}