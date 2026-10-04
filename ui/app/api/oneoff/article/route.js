import { NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function POST(request) {
  try {
    const body = await request.json();

    if (!body.url) {
      return NextResponse.json({ error: 'url is required' }, { status: 400 });
    }

    const response = await fetch(`${API_BASE_URL}/oneoff/article`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        { error: data.detail || 'Conversion failed' },
        { status: response.status }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Error converting article:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
