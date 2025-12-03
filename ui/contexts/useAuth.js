'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { createClient } from '../lib/supabase'

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
    const supabase = createClient()

    useEffect(() => {
        // Get initial session
        const getSession = async () => {
            const { data: { session }, error } = await supabase.auth.getSession()
            if (error) {
                console.error('Error getting session:', error)
            } else {
                setSession(session)
                setUser(session?.user ?? null)
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
                console.log('User signed in:', session?.user?.email)
            }

            // Handle sign out event
            if (event === 'SIGNED_OUT') {
                console.log('User signed out')
            }
        })

        return () => subscription?.unsubscribe()
    }, [])

    const signInWithMagicLink = async (email) => {
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

            console.log('🧹 Cleared localStorage: newsletterConfig, selectedPublications, guestSessionId')

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