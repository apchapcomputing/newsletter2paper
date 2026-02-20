import { NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function DELETE(request, context) {
    try {
        const params = await context.params;
        const { issueId } = params;

        // Forward DELETE request to Python backend
        const response = await fetch(`${API_URL}/issues/${issueId}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            const errorText = await response.text();
            return NextResponse.json(
                { error: 'Failed to delete issue', details: errorText },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Error in DELETE /api/issues/[issueId]:', error);
        return NextResponse.json(
            { error: 'Internal server error', details: error.message },
            { status: 500 }
        );
    }
}
