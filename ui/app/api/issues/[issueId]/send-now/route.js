import { NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request, context) {
    try {
        const { issueId } = await context.params;

        const response = await fetch(`${API_URL}/issues/${issueId}/send-now`, { method: 'POST' });
        const body = await response.json().catch(() => ({}));

        if (!response.ok) {
            return NextResponse.json(
                { error: body.detail || 'Failed to start sending' },
                { status: response.status }
            );
        }
        return NextResponse.json(body, { status: response.status });
    } catch (error) {
        console.error('Error in POST /api/issues/[issueId]/send-now:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}
