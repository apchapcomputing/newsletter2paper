import { createClient } from '../lib/supabase'

/**
 * Utility for making authenticated API calls to the Python backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export class AuthenticatedAPI {
    constructor() {
        this.supabase = createClient()
    }

    async getAuthHeaders() {
        const { data: { session } } = await this.supabase.auth.getSession()

        if (session?.access_token) {
            return {
                'Authorization': `Bearer ${session.access_token}`,
                'Content-Type': 'application/json'
            }
        }

        return {
            'Content-Type': 'application/json'
        }
    }

    async makeRequest(endpoint, options = {}) {
        const headers = await this.getAuthHeaders()

        const config = {
            ...options,
            headers: {
                ...headers,
                ...options.headers
            }
        }

        const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`

        try {
            const response = await fetch(url, config)

            if (!response.ok) {
                let errorData
                try {
                    errorData = await response.json()
                } catch {
                    errorData = { message: response.statusText }
                }

                throw new Error(errorData.message || errorData.detail || `HTTP ${response.status}`)
            }

            // Handle responses that might not have JSON body
            const contentType = response.headers.get('content-type')
            if (contentType && contentType.includes('application/json')) {
                return await response.json()
            } else {
                return { success: true, data: await response.text() }
            }
        } catch (error) {
            console.error(`API request failed for ${endpoint}:`, error)
            throw error
        }
    }

    // HTTP method shortcuts
    async get(endpoint, params = {}) {
        const url = new URL(endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`)
        Object.keys(params).forEach(key => {
            if (params[key] !== undefined && params[key] !== null) {
                url.searchParams.append(key, params[key])
            }
        })

        return this.makeRequest(url.toString(), { method: 'GET' })
    }

    async post(endpoint, data = {}) {
        return this.makeRequest(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        })
    }

    async put(endpoint, data = {}) {
        return this.makeRequest(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        })
    }

    async delete(endpoint) {
        return this.makeRequest(endpoint, { method: 'DELETE' })
    }
}

// Create a singleton instance
const authenticatedAPI = new AuthenticatedAPI()

export default authenticatedAPI

// Export convenience methods
export const apiGet = (endpoint, params) => authenticatedAPI.get(endpoint, params)
export const apiPost = (endpoint, data) => authenticatedAPI.post(endpoint, data)
export const apiPut = (endpoint, data) => authenticatedAPI.put(endpoint, data)
export const apiDelete = (endpoint) => authenticatedAPI.delete(endpoint)