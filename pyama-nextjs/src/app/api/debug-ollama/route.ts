export async function GET() {
  try {
    const ollamaUrl = 'http://localhost:11434/api/tags';
    const response = await fetch(ollamaUrl);
    const data = await response.json();
    
    return Response.json({
      status: 'success',
      data,
      message: 'Connected to Ollama!'
    });
  } catch (error: any) {
    return Response.json({
      status: 'error',
      message: error?.message || 'Failed to connect to Ollama',
      error: error?.toString(),
      errorType: error?.name || typeof error
    });
  }
}
