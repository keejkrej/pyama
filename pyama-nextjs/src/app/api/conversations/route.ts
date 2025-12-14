import { ConvexHttpClient } from 'convex/browser';
import { NextRequest, NextResponse } from 'next/server';
import { api } from '../../../lib/convex.js';

const convex = new ConvexHttpClient(process.env.NEXT_PUBLIC_CONVEX_URL!);

export async function GET() {
  try {
    const conversations = await convex.query(api.conversations.list);
    return NextResponse.json(conversations);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch conversations' }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const { title, firstMessage } = await req.json();
    
    // Create conversation
    const conversationId = await convex.mutation(api.conversations.create, {
      title: title || 'New Chat',
      model: 'gemma3:latest',
    });

    // Send first message if provided
    if (firstMessage) {
      await convex.mutation(api.messages.send, {
        conversationId,
        role: firstMessage.role,
        content: firstMessage.content,
      });
    }

    const conversation = await convex.query(api.conversations.get, { id: conversationId });
    return NextResponse.json(conversation);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to create conversation' }, { status: 500 });
  }
}
