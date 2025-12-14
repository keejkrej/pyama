import { useState, useEffect } from 'react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export function usePersistentChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

  // Load existing conversation on mount
  useEffect(() => {
    async function loadConversation() {
      try {
        // Get or create a conversation
        let convId = localStorage.getItem('activeConversationId')
        
        if (!convId) {
          // Create new conversation
          const response = await fetch('/api/conversations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: 'New Conversation',
            }),
          })
          const conversation = await response.json()
          convId = conversation._id
          localStorage.setItem('activeConversationId', convId)
        } else {
          // Load existing messages
          const messagesResponse = await fetch(`/api/conversations/${convId}`)
          const existingMessages = await messagesResponse.json()
          setMessages(existingMessages.map((m: any) => ({
            id: m._id,
            role: m.role,
            content: m.content,
          }))
        }
        
        setConversationId(convId)
      } catch (error) {
        console.error('Failed to load conversation:', error)
      } finally {
        setLoaded(true)
      }
    }
    
    loadConversation()
  }, [])

  const saveMessage = async (message: Omit<Message, 'id'>) => {
    if (!conversationId) return

    try {
      const response = await fetch('/api/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversationId,
          ...message,
        }),
      })

      if (!response.ok) throw new Error('Failed to save message')
      
      return await response.json()
    } catch (error) {
      console.error('Failed to save message:', error)
    }
  }

  const startNewConversation = async () => {
    try {
      const response = await fetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Conversation' }),
      })
      
      const conversation = await response.json()
      const newId = conversation._id
      
      setConversationId(newId)
      setMessages([])
      localStorage.setItem('activeConversationId', newId)
      
      return newId
    } catch (error) {
      console.error('Failed to create conversation:', error)
    }
  }

  return {
    messages,
    setMessages,
    conversationId,
    saveMessage,
    startNewConversation,
    loaded,
  }
}
