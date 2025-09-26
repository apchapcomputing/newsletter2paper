import { NextResponse } from 'next/server';

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get('query');
    
    if (!query) {
      return NextResponse.json({ error: 'Query parameter is required' }, { status: 400 });
    }

    // Make the request to Substack API from the server
    const substackResponse = await fetch(
      `https://substack.com/api/v1/platform/search?query=${encodeURIComponent(query)}`,
      {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'Mozilla/5.0 (compatible; Newsletter2Paper/1.0)',
        },
      }
    );

    if (!substackResponse.ok) {
      throw new Error(`Substack API error: ${substackResponse.status}`);
    }

    const data = await substackResponse.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error proxying Substack search:', error);
    return NextResponse.json(
      { error: 'Failed to search Substack' }, 
      { status: 500 }
    );
  }
}
