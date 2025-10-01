import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request) {
    try {
        const url = new URL(request.url);
        const action = url.searchParams.get('action');
        const body = await request.json();

        let endpoint = '/publications/';

        // Handle different publication actions
        if (action === 'find-or-create') {
            endpoint = '/publications/find-or-create';
        }

        // Forward the request to the Python backend
        const response = await fetch(`${BACKEND_URL}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            const errorData = await response.text();
            return NextResponse.json(
                { error: 'Failed to process publication request', details: errorData },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);

    } catch (error) {
        console.error('Error processing publication request:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}

export async function GET(request) {
    try {
        const url = new URL(request.url);
        const search = url.searchParams.get('search');
        const publicationId = url.searchParams.get('id');

        let endpoint = '/publications/';

        if (publicationId) {
            endpoint = `/publications/${publicationId}`;
        } else if (search) {
            endpoint = `/publications/?search=${encodeURIComponent(search)}`;
        }

        // Forward the request to the Python backend
        const response = await fetch(`${BACKEND_URL}${endpoint}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            const errorData = await response.text();
            return NextResponse.json(
                { error: 'Failed to get publications', details: errorData },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);

    } catch (error) {
        console.error('Error getting publications:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}