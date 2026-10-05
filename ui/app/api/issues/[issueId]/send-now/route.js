import { NextResponse } from 'next/server';
import { tracingHeaders } from '@/lib/tracingHeaders';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request, context) {
    try {
        const { issueId } = await context.params;

        const authorization = request.headers.get('authorization');
        if (!authorization) {
            return NextResponse.json({ error: 'Sign in to send now' }, { status: 401 });
        }

        // The backend verifies this Supabase access token and checks the caller owns the issue.
        const response = await fetch(`${API_URL}/issues/${issueId}/send-now`, {
            method: 'POST',
            headers: { Authorization: authorization, ...tracingHeaders(request) },
        });
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
