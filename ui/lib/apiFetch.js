import { createClient } from './supabase'
import { createGuestTokenFetch } from './guestTokenFetch'

// fetch() for our own /api/* routes: adds the signed-in user's access token and the guest
// token so the backend can tell whose issue is being touched.
export async function apiFetch(input, init = {}) {
    const headers = new Headers(init.headers)
    if (!headers.has('Authorization')) {
        try {
            const { data } = await createClient().auth.getSession()
            if (data?.session?.access_token) {
                headers.set('Authorization', `Bearer ${data.session.access_token}`)
            }
        } catch {
            // no session available: fall back to the guest token alone
        }
    }
    return createGuestTokenFetch()(input, { ...init, headers })
}
