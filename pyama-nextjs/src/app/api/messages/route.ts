import { ConvexHttpClient } from 'convex/browser';
import { NextResponse } from 'next/server';
import { api } from '../../../lib/convex.js';

const convex = new ConvexHttpClient(process.env.NEXT_PUBLIC_CONVEX_URL!);

export async function POST(req: Request) {
  try {
    const { conversationId, role, content } = await req.json();
    
    const messageId = await convex.mutation(api.messages.send, {
      conversationId,
      role,
      content,
    });

    return NextResponse.json({ id: messageId });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to save message' }, { status: 500 });
  }
}
