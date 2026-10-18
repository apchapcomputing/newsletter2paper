'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { createClient } from '../lib/supabase'
import logger from '../utils/logger'
import { identify, reset, track } from '../lib/analytics'

// Set by app/auth/callback after a successful sign-in, so the completion event fires once per
// sign-in rather than on every session restore.
export const AUTH_COMPLETED_PARAM = 'signed_in'
const NEW_ACCOUNT_MS = 10 * 60 * 1000

export function trackCompletedSignIn(user) {
    if (typeof window === 'undefined' || !user) return
    const url = new URL(window.location.href)
    if (!url.searchParams.has(AUTH_COMPLETED_PARAM)) return
    url.searchParams.delete(AUTH_COMPLETED_PARAM)
    window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash)
    const isNew = Date.now() - new Date(user.created_at).getTime() < NEW_ACCOUNT_MS
    track(isNew ? 'signup_completed' : 'signed_in', { method: user.app_metadata?.provider || 'email' })
}

const AuthContext = createContext({
    user: null,
    session: null,
    signInWithMagicLink: async () => { },
    signInWithProvider: async () => { },
    signOut: async () => { },
    loading: true
})

export const useAuth = () => {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null)
    const [session, setSession] = useState(null)
    const [loading, setLoading] = useState(true)
    // Create the client once, not on every render.
    const [supabase] = useState(() => createClient())

    useEffect(() => {
        // Get initial session
        const getSession = async () => {
            const { data: { session }, error } = await supabase.auth.getSession()
            if (error) {
                console.error('Error getting session:', error)
            } else {
                setSession(session)
                setUser(session?.user ?? null)
                identify(session?.user?.id)
                trackCompletedSignIn(session?.user)
            }
            setLoading(false)
        }

        getSession()

        // Listen for auth changes
        const {
            data: { subscription },
        } = supabase.auth.onAuthStateChange(async (event, session) => {
            setSession(session)
            setUser(session?.user ?? null)
            setLoading(false)

            // Handle sign in event
            if (event === 'SIGNED_IN') {
                identify(session?.user?.id)
                logger.log('User signed in:', session?.user?.email)
            }

            // Handle sign out event
            if (event === 'SIGNED_OUT') {
                reset() // also covers sign-out from another tab or an expired session
                logger.log('User signed out')
            }
        })

        return () => subscription?.unsubscribe()
    }, [supabase])

    const signInWithMagicLink = async (email) => {
        track('signup_started', { method: 'email' })
        try {
            const { data, error } = await supabase.auth.signInWithOtp({
                email,
                options: {
                    emailRedirectTo: `${window.location.origin}/auth/callback`
                }
            })

            if (error) throw error

            return { success: true, data }
        } catch (error) {
            console.error('Error signing in with magic link:', error)
            return { success: false, error: error.message }
        }
    }

    const signInWithProvider = async (provider) => {
        track('signup_started', { method: provider })
        try {
            const { data, error } = await supabase.auth.signInWithOAuth({
                provider,
                options: {
                    redirectTo: `${window.location.origin}/auth/callback`
                }
            })

            if (error) throw error

            return { success: true, data }
        } catch (error) {
            console.error(`Error signing in with ${provider}:`, error)
            return { success: false, error: error.message }
        }
    }

    const signOut = async () => {
        try {
            const { error } = await supabase.auth.signOut()
            if (error) throw error

            // Clear local state
            setUser(null)
            setSession(null)

            // Clear all localStorage data related to the issue configuration
            localStorage.removeItem('newsletterConfig')
            localStorage.removeItem('selectedPublications')
            localStorage.removeItem('guestSessionId')

            logger.log('🧹 Cleared localStorage: newsletterConfig, selectedPublications, guestSessionId')

            return { success: true }
        } catch (error) {
            console.error('Error signing out:', error)
            return { success: false, error: error.message }
        }
    }

    const value = {
        user,
        session,
        signInWithMagicLink,
        signInWithProvider,
        signOut,
        loading
    }

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    )
}