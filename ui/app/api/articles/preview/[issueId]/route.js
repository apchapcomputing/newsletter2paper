import logger from '@/utils/logger';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET(request, { params }) {
    try {
        const { issueId } = await params;
        const { searchParams } = new URL(request.url);
        const daysBack = searchParams.get('days_back') || '7';
        const publicationId = searchParams.get('publication_id'); // Optional filter
        const startDate = searchParams.get('start_date');
        const endDate = searchParams.get('end_date');

        if (!issueId) {
            return new Response(
                JSON.stringify({ error: 'Issue ID is required' }),
                { status: 400, headers: { 'Content-Type': 'application/json' } }
            );
        }

        // Fetch article previews from the backend
        const backendUrl = `${BACKEND_URL}/articles/fetch/${issueId}`;
        const backendSearchParams = new URLSearchParams({
            max_articles_per_publication: '10' // Get up to 10 articles per publication for preview
        });

        // Use explicit date window if provided, otherwise fall back to days_back
        if (startDate && endDate) {
            backendSearchParams.append('start_date', startDate);
            backendSearchParams.append('end_date', endDate);
        } else {
            backendSearchParams.append('days_back', daysBack);
        }

        // Add publication_id if filtering for single publication
        if (publicationId) {
            backendSearchParams.append('publication_id', publicationId);
        }

        logger.log(`Fetching article preview from: ${backendUrl}?${backendSearchParams}`);

        const response = await fetch(`${backendUrl}?${backendSearchParams}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                days_back: startDate ? null : parseInt(daysBack),
                max_articles_per_publication: 10,
            })
        });

        if (!response.ok) {
            const errorData = await response.text();
            console.error('Backend error:', errorData);
            return new Response(
                JSON.stringify({
                    error: 'Failed to fetch article preview',
                    details: errorData
                }),
                {
                    status: response.status,
                    headers: { 'Content-Type': 'application/json' }
                }
            );
        }

        const data = await response.json();

        return new Response(
            JSON.stringify(data),
            {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            }
        );

    } catch (error) {
        console.error('Error fetching article preview:', error);
        return new Response(
            JSON.stringify({
                error: 'Internal server error',
                details: error.message
            }),
            {
                status: 500,
                headers: { 'Content-Type': 'application/json' }
            }
        );
    }
}
