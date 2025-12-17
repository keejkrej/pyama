import { ConvexHttpClient } from 'convex/browser'
import { NextRequest, NextResponse } from 'next/server'
import { api } from '../../../../lib/convex.js'

const convex = new ConvexHttpClient(process.env.NEXT_PUBLIC_CONVEX_URL!)

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const conversation = await convex.query(api.conversations.get, { 
      id: params.id as any 
    })
    
    if (!conversation) {
      return NextResponse.json({ error: 'Conversation not found' }, { status: 404 })
    }
    
    return NextResponse.json(conversation)
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch conversation' }, { status: 500 })
  }
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { title } = await req.json()
    
    if (!title) {
      return NextResponse.json({ error: 'Title is required' }, { status: 400 })
    }
    
    await convex.mutation(api.conversations.updateTitle, {
      id: params.id as any,
      title,
    })
    
    const conversation = await convex.query(api.conversations.get, { 
      id: params.id as any 
    })
    
    return NextResponse.json(conversation)
  } catch (error) {
    return NextResponse.json({ error: 'Failed to update conversation' }, { status: 500 })
  }
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await convex.mutation(api.conversations.remove, { 
      id: params.id as any 
    })
    
    return NextResponse.json({ success: true })
  } catch (error) {
    return NextResponse.json({ error: 'Failed to delete conversation' }, { status: 500 })
  }
}
