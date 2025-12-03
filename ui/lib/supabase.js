import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
    // Provide fallback values for build time when env vars might not be available
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder.supabase.co'
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder-key'

    // Get the site URL from environment variables
    // This allows proper redirect URLs for different environments (local, dev, prod)
    const siteUrl = process.env.NEXT_PUBLIC_UI_URL ||
        (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000')

    return createBrowserClient(
        supabaseUrl,
        supabaseAnonKey,
        {
            auth: {
                redirectTo: `${siteUrl}/auth/callback`,
                autoRefreshToken: true,
                persistSession: true,
                detectSessionInUrl: true
            }
        }
    )
}