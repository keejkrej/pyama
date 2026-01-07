export const runtime = 'nodejs';

export async function POST() {
  try {
    const response = await fetch('http://localhost:11434/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'gemma3:latest',
        messages: [{ role: 'user', content: 'hi' }],
        stream: false,  // Try without streaming first
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      return Response.json({ 
        error: 'Failed to fetch from Ollama',
        status: response.status,
        details: errorText 
      }, { status: 500 });
    }

    const data = await response.json();
    return Response.json(data);
  } catch (error: any) {
    return Response.json({ 
      error: error.message,
      stack: error.stack 
    }, { status: 500 });
  }
}
