// Server-side helper for the app/api proxies: pass the caller's credentials on to the
// FastAPI backend, which authorizes every issue route (Supabase access token for owners,
// per-browser guest token for guest issues).
export function authHeaders(request) {
    const headers = {}
    const authorization = request.headers.get('authorization')
    if (authorization) headers.Authorization = authorization
    const guestToken = request.headers.get('x-guest-token')
    if (guestToken) headers['x-guest-token'] = guestToken
    return headers
}
