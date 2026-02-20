import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request) {
    try {
        const url = new URL(request.url);
        const pathParts = url.pathname.split('/');
        const issueId = pathParts[pathParts.length - 2]; // Get issue ID from path

        if (!issueId) {
            return NextResponse.json(
                { error: 'Issue ID is required' },
                { status: 400 }
            );
        }

        const body = await request.json();

        // Forward the request to the Python backend
        const response = await fetch(`${BACKEND_URL}/issues/${issueId}/publications`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            const errorData = await response.text();
            return NextResponse.json(
                { error: 'Failed to add publications to issue', details: errorData },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);

    } catch (error) {
        console.error('Error adding publications to issue:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}

export async function GET(request) {
    try {
        const url = new URL(request.url);
        const pathParts = url.pathname.split('/');
        const issueId = pathParts[pathParts.length - 2]; // Get issue ID from path

        if (!issueId) {
            return NextResponse.json(
                { error: 'Issue ID is required' },
                { status: 400 }
            );
        }

        // Forward the request to the Python backend
        const response = await fetch(`${BACKEND_URL}/issues/${issueId}/publications`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            const errorData = await response.text();
            return NextResponse.json(
                { error: 'Failed to get issue publications', details: errorData },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);

    } catch (error) {
        console.error('Error getting issue publications:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}