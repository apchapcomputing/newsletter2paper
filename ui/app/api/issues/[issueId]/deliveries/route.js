import { NextResponse } from 'next/server';
import { tracingHeaders } from '@/lib/tracingHeaders';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// The issue's recent editions (owner only; the backend checks ownership).
export async function GET(request, context) {
    try {
        const { issueId } = await context.params;

        const authorization = request.headers.get('authorization');
        if (!authorization) {
            return NextResponse.json({ error: 'Sign in to see delivery history' }, { status: 401 });
        }

        const limit = new URL(request.url).searchParams.get('limit');
        const query = limit ? `?limit=${encodeURIComponent(limit)}` : '';
        const response = await fetch(`${API_URL}/issues/${issueId}/deliveries${query}`, {
            headers: { Authorization: authorization, ...tracingHeaders(request) },
        });
        const body = await response.json().catch(() => ({}));

        if (!response.ok) {
            return NextResponse.json(
                { error: body.detail || 'Could not load delivery history' },
                { status: response.status }
            );
        }
        return NextResponse.json(body);
    } catch (error) {
        console.error('Error in GET /api/issues/[issueId]/deliveries:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}
