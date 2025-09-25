import { NextResponse } from 'next/server';

// Get API URL from environment variables
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function GET(request) {
  try {
    // Get the webpage_url from the query parameters
    const { searchParams } = new URL(request.url);
    const webpageUrl = searchParams.get('webpage_url');

    if (!webpageUrl) {
      return NextResponse.json(
        { error: 'webpage_url parameter is required' },
        { status: 400 }
      );
    }

    // Call the Python FastAPI endpoint
    const response = await fetch(
      `${API_BASE_URL}/rss/url?webpage_url=${encodeURIComponent(webpageUrl)}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      return NextResponse.json(
        { error: errorData.detail || 'Failed to fetch RSS URL' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching RSS URL:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}