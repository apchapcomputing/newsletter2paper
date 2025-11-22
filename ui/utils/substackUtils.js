/**
 * Utility functions for Substack API interactions
 */

/**
 * Search for publications and users on Substack
 * @param {string} query - The search term
 * @returns {Promise<Array>} - Array of formatted publication objects
 */
export const searchSubstack = async (query) => {
    if (!query.trim()) {
        return [];
    }

    try {
        const response = await fetch(`/api/substack/search?query=${encodeURIComponent(query)}`);
        if (!response.ok) {
            throw new Error(`Error: ${response.statusText}`);
        }
        const data = await response.json();
        console.log('Substack search results:', data);

        // Parse results to extract publication names
        const publications = data.results?.map(result => {
            if (result.type === 'user') {
                const u = result.user;
                return {
                    name: u?.publication_name || u?.name || 'Unknown Publication',
                    publisher: u?.name || 'Unknown Publisher',
                    type: 'user',
                    handle: u?.handle,
                    subdomain: u?.handle, // For constructing URLs
                    subscribers: u?.subscriber_count_string
                };
            } else if (result.type === 'publication') {
                const p = result.publication;
                const domain = p?.subdomain + '.substack.com';
                return {
                    name: p?.name || 'Unknown Publication',
                    publisher: p?.author_name || 'Unknown Publisher',
                    type: 'publication',
                    domain: p?.custom_domain || domain,
                    subscribers: p?.subscriber_count_string
                };
            }
            return null;
        }).filter(Boolean) || [];
        console.log(publications);
        return publications;
    } catch (error) {
        console.error("Failed to search Substack:", error);
        return [];
    }
};