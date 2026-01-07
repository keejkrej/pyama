import { ConvexHttpClient } from 'convex/browser'
import { NextRequest, NextResponse } from 'next/server'
import { api } from '../../../../../lib/convex.js'

const convex = new ConvexHttpClient(process.env.NEXT_PUBLIC_CONVEX_URL!)

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const messages = await convex.query(api.messages.listByConversation, {
      conversationId: params.id as any,
    })
    
    return NextResponse.json(messages)
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch messages' }, { status: 500 })
  }
}
