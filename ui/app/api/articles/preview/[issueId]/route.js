const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET(request, { params }) {
    try {
        const issueId = params.issueId;
        const { searchParams } = new URL(request.url);
        const daysBack = searchParams.get('days_back') || '7';

        if (!issueId) {
            return new Response(
                JSON.stringify({ error: 'Issue ID is required' }),
                { status: 400, headers: { 'Content-Type': 'application/json' } }
            );
        }

        // Fetch article previews from the backend
        const backendUrl = `${BACKEND_URL}/articles/fetch/${issueId}`;
        const backendSearchParams = new URLSearchParams({
            days_back: daysBack,
            max_articles_per_publication: '10' // Get up to 10 articles per publication for preview
        });

        console.log(`Fetching article preview from: ${backendUrl}?${backendSearchParams}`);

        const response = await fetch(`${backendUrl}?${backendSearchParams}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                days_back: parseInt(daysBack),
                max_articles_per_publication: 10
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
