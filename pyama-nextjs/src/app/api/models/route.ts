import { NextResponse } from "next/server";

const BASE_URL = process.env.OPENAI_BASE_URL || 'http://localhost:11434/v1';

export async function GET() {
  try {
    const response = await fetch(`${BASE_URL}/models`, {
      headers: {
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY || 'ollama'}`
      }
    });
    
    if (!response.ok) {
      console.error('Model fetch error:', response.status, response.statusText);
      return NextResponse.json({ models: [] });
    }

    const data = await response.json();
    const models: string[] = data.data?.map((m: any) => m.id) ?? [];
    
    return NextResponse.json({ models });
  } catch (error) {
    console.error("Error fetching models:", error);
    return NextResponse.json({ models: [] });
  }
}
