import { NextResponse } from 'next/server';
import logger from '@/utils/logger';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function POST(request, { params }) {
    try {
        const { issueId } = await params;
        const url = new URL(request.url);

        // Extract query parameters from the frontend request
        const searchParams = new URLSearchParams();

        // Only pass layout_type if explicitly provided (to override DB value)
        const layoutType = url.searchParams.get('layout_type');
        if (layoutType) {
            searchParams.append('layout_type', layoutType);
        }

        // Only pass remove_images if explicitly provided (to override DB value)
        const removeImages = url.searchParams.get('remove_images');
        if (removeImages !== null) {
            searchParams.append('remove_images', removeImages);
        }

        // Add other optional parameters with defaults
        searchParams.append('days_back', url.searchParams.get('days_back') || '7');
        searchParams.append('max_articles_per_publication', url.searchParams.get('max_articles_per_publication') || '5');
        searchParams.append('keep_html', url.searchParams.get('keep_html') || 'false');
        searchParams.append('verbose', url.searchParams.get('verbose') || 'false');

        // Make request to the Python backend
        const backendUrl = `${API_BASE_URL}/pdf/generate/${issueId}?${searchParams.toString()}`;

        logger.log('Making request to backend:', backendUrl);

        const response = await fetch(backendUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            body: JSON.stringify({}), // Empty body as required by the backend
        });

        const data = await response.json();

        if (!response.ok) {
            console.error('Backend error:', data);
            return NextResponse.json(
                {
                    success: false,
                    message: data.detail || 'PDF generation failed',
                    error: data
                },
                { status: response.status }
            );
        }

        logger.log('PDF generation successful:', data);

        return NextResponse.json({
            success: true,
            message: 'PDF generated successfully',
            pdf_url: data.pdf_url,
            issue_info: data.issue_info,
            articles_count: data.articles_count
        });

    } catch (error) {
        console.error('Error in PDF generation API route:', error);

        return NextResponse.json(
            {
                success: false,
                message: 'Internal server error during PDF generation',
                error: error.message
            },
            { status: 500 }
        );
    }
}