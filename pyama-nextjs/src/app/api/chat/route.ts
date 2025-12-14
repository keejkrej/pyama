import { ConvexHttpClient } from 'convex/browser';
import { api } from '../../../lib/convex.js';

const BASE_URL = process.env.OPENAI_BASE_URL || 'http://localhost:11434/v1';

export const runtime = 'nodejs';

export async function POST(req: Request) {
  const { messages, model, conversationId } = await req.json();
  
  const selectedModel = model || 'gemma3:latest';
  
  console.log('Chat request:', { 
    model: selectedModel,
    messageCount: messages.length,
    conversationId,
    baseUrl: BASE_URL
  });
  
  try {
    // Save user message to Convex if we have a conversation
    if (conversationId && messages.length > 0) {
      const convex = new ConvexHttpClient(process.env.NEXT_PUBLIC_CONVEX_URL!);
      const lastMessage = messages[messages.length - 1];
      await convex.mutation(api.messages.send, {
        conversationId,
        role: lastMessage.role,
        content: lastMessage.content,
      });
    }

    // Use streaming with OpenAI-compatible endpoint
    const response = await fetch(`${BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY || 'ollama'}`
      },
      body: JSON.stringify({
        model: selectedModel,
        messages: messages.map((m: any) => ({
          role: m.role,
          content: m.content,
        })),
        stream: true,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('API error:', response.status, errorText);
      throw new Error(`API error: ${response.status} - ${errorText}`);
    }

    // Return the streaming response directly
    return new Response(response.body, {
      headers: { 'Content-Type': 'text/event-stream' },
    });
  } catch (error: any) {
    console.error('Chat error:', error);
    return Response.json({ error: error.message }, { status: 500 });
  }
}
