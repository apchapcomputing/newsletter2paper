/**
 * Utility functions for Substack API interactions
 */

import logger from './logger';

/**
 * Capitalize each word in a name properly
 * @param {string} name - The name to capitalize
 * @returns {string} - Properly capitalized name
 */
const capitalizeName = (name) => {
    if (!name) return name;

    // Particles stay lowercase mid-name ("Ludwig van Beethoven") but start a name capitalised ("Van Jones").
    const particles = ['von', 'de', 'van', 'der', 'da', 'di'];
    return name
        .split(' ')
        .map((word, index) => {
            if (!word) return word;
            if (index > 0 && particles.includes(word.toLowerCase())) {
                return word.toLowerCase();
            }
            // Capitalize the first letter only; keep the rest as typed to preserve names like McDonald
            return word.charAt(0).toUpperCase() + word.slice(1);
        })
        .join(' ');
};

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
            const errorData = await response.json().catch(() => ({}));
            console.error('Search API error:', response.status, errorData);
            throw new Error(`Error: ${response.statusText} - ${errorData.details || errorData.error || 'Unknown error'}`);
        }
        const data = await response.json();
        logger.log('Substack search results:', data);

        // Parse results to extract publication names
        const publications = data.results?.map(result => {
            if (result.type === 'user') {
                const u = result.user;
                return {
                    name: u?.publication_name || u?.name || 'Unknown Publication',
                    publisher: capitalizeName(u?.name) || 'Unknown Publisher',
                    type: 'user',
                    handle: u?.handle,
                    subdomain: u?.handle, // For constructing URLs
                    subscribers: u?.subscriber_count_string
                };
            } else if (result.type === 'publication') {
                const p = result.publication;
                const domain = p?.subdomain ? p.subdomain + '.substack.com' : undefined;
                return {
                    name: p?.name || 'Unknown Publication',
                    publisher: capitalizeName(p?.author_name) || 'Unknown Publisher',
                    type: 'publication',
                    domain: p?.custom_domain || domain,
                    subscribers: p?.subscriber_count_string
                };
            }
            return null;
        }).filter(Boolean) || [];
        logger.log(publications);
        return publications;
    } catch (error) {
        console.error("Failed to search Substack:", error);
        return [];
    }
};