export const getRssFeedUrl = async (url) => {
    try {
        const response = await fetch(`/api/rss/url?webpage_url=${encodeURIComponent(url)}`);
        if (!response.ok) {
            throw new Error(`Error: ${response.statusText}`);
        }
        const data = await response.json();
        return data.feed_url;
    } catch (error) {
        console.error("Failed to fetch RSS feed URL:", error);
    }
}