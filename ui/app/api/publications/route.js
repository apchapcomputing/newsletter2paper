import { readFileSync } from 'fs';
import { join } from 'path';
import { NextResponse } from 'next/server';

export async function GET() {
  try {
    // Read the CSV file
    const filePath = join(process.cwd(), 'data', 'publications.csv');
    console.log('Reading publications from:', filePath);
    const fileContent = readFileSync(filePath, 'utf-8');
    
    // Parse CSV content
    const lines = fileContent.trim().split('\n');
    const headers = lines[0].split(',').map(header => header.trim());
    
    const publications = lines.slice(1).map(line => {
      const values = line.split(',').map(value => value.trim());
      return headers.reduce((obj, header, index) => {
        obj[header] = values[index];
        return obj;
      }, {});
    });

    return NextResponse.json({ publications });
  } catch (error) {
    console.error('Error reading publications:', error);
    return NextResponse.json(
      { error: 'Failed to load publications' },
      { status: 500 }
    );
  }
}