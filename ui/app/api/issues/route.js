import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request) {
    try {
        const body = await request.json();

        // Forward the request to the Python backend
        const response = await fetch(`${BACKEND_URL}/issues/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            const errorData = await response.text();
            return NextResponse.json(
                { error: 'Failed to create issue', details: errorData },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);

    } catch (error) {
        console.error('Error creating issue:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}

export async function PUT(request) {
    try {
        const url = new URL(request.url);
        const issueId = url.searchParams.get('id');

        if (!issueId) {
            return NextResponse.json(
                { error: 'Issue ID is required for updates' },
                { status: 400 }
            );
        }

        const body = await request.json();

        // Forward the request to the Python backend
        const response = await fetch(`${BACKEND_URL}/issues/${issueId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            const errorData = await response.text();
            return NextResponse.json(
                { error: 'Failed to update issue', details: errorData },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);

    } catch (error) {
        console.error('Error updating issue:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}

export async function GET(request) {
    try {
        const url = new URL(request.url);
        const issueId = url.searchParams.get('id');

        if (!issueId) {
            return NextResponse.json(
                { error: 'Issue ID is required' },
                { status: 400 }
            );
        }

        // Forward the request to the Python backend
        const response = await fetch(`${BACKEND_URL}/issues/${issueId}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            const errorData = await response.text();
            return NextResponse.json(
                { error: 'Failed to get issue', details: errorData },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);

    } catch (error) {
        console.error('Error getting issue:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}
