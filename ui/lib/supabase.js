import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
    // Provide fallback values for build time when env vars might not be available
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder.supabase.co'
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder-key'

    // Get the site URL from environment variables
    // This allows proper redirect URLs for different environments (local, dev, prod)
    const siteUrl = process.env.NEXT_PUBLIC_UI_URL ||
        (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000')

    // Debug log to help diagnose failed network calls during auth refresh
    if (typeof window !== 'undefined' && window?.console?.debug) {
        // Don't log sensitive keys; only log the URL and redirect target
        console.debug('[supabase] using url:', supabaseUrl, 'redirectTo:', `${siteUrl}/auth/callback`)
    }

    return createBrowserClient(
        supabaseUrl,
        supabaseAnonKey,
        {
            global: {
                // Guest issues are protected by RLS with a per-browser secret (see
                // supabase/migrations/*_enable_rls.sql). Read it per request so it is
                // picked up as soon as saveGuestIssue creates it.
                fetch: (input, init = {}) => {
                    let token = null
                    try { token = typeof window !== 'undefined' ? window.localStorage.getItem('guestSessionId') : null } catch { /* storage unavailable */ }
                    if (!token) return fetch(input, init)
                    const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined))
                    headers.set('x-guest-token', token)
                    return fetch(input, { ...init, headers })
                }
            },
            auth: {
                redirectTo: `${siteUrl}/auth/callback`,
                autoRefreshToken: true,
                persistSession: true,
                detectSessionInUrl: true
            }
        }
    )
}