import { NextResponse } from 'next/server';
import { tracingHeaders } from '@/lib/tracingHeaders';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Asks the backend to email the issue's target address a confirmation link.
export async function POST(request, context) {
    try {
        const { issueId } = await context.params;

        const authorization = request.headers.get('authorization');
        if (!authorization) {
            return NextResponse.json({ error: 'Sign in to confirm an address' }, { status: 401 });
        }

        const response = await fetch(`${API_URL}/issues/${issueId}/target-email/verify`, {
            method: 'POST',
            headers: { Authorization: authorization, ...tracingHeaders(request) },
        });
        const body = await response.json().catch(() => ({}));

        if (!response.ok) {
            return NextResponse.json(
                { error: body.detail || 'Could not send the confirmation email' },
                { status: response.status }
            );
        }
        return NextResponse.json(body, { status: response.status });
    } catch (error) {
        console.error('Error in POST /api/issues/[issueId]/target-email/verify:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}
