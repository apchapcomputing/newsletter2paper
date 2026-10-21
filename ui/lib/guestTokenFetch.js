// Guest issues are protected by RLS with a per-browser secret (see
// newsletter2paper/supabase/migrations/*_enable_rls.sql). The token lives in
// localStorage under `guestSessionId`; it is read per request so it is picked up as soon
// as saveGuestIssue creates it.
export const GUEST_TOKEN_STORAGE_KEY = 'guestSessionId'
export const GUEST_TOKEN_HEADER = 'x-guest-token'

function readGuestToken() {
    try {
        return typeof window !== 'undefined' ? window.localStorage.getItem(GUEST_TOKEN_STORAGE_KEY) : null
    } catch {
        return null // storage unavailable (private mode, blocked site data)
    }
}

export function createGuestTokenFetch(baseFetch = (...args) => fetch(...args)) {
    return (input, init = {}) => {
        const token = readGuestToken()
        if (!token) return baseFetch(input, init)
        const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined))
        headers.set(GUEST_TOKEN_HEADER, token)
        return baseFetch(input, { ...init, headers })
    }
}
