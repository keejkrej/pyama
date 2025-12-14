'use client'

import { useEffect, useState, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sidebar } from '@/components/Sidebar'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [models, setModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Load conversation messages when conversationId changes
  useEffect(() => {
    async function loadMessages() {
      if (!conversationId) {
        setMessages([])
        return
      }
      
      try {
        const response = await fetch(`/api/conversations/${conversationId}/messages`)
        if (response.ok) {
          const existingMessages = await response.json()
          setMessages(existingMessages.map((m: any) => ({
            id: m._id,
            role: m.role,
            content: m.content,
          })))
        } else {
          setMessages([])
        }
      } catch (error) {
        console.error('Failed to load messages:', error)
        setMessages([])
      }
    }
    
    loadMessages()
  }, [conversationId])

  // Initialize conversation on mount
  useEffect(() => {
    const savedConvId = localStorage.getItem('activeConversationId')
    if (savedConvId) {
      setConversationId(savedConvId)
    } else {
      // Will be created by new chat
      handleNewChat()
    }
  }, [])

  useEffect(() => {
    async function fetchModels() {
      try {
        const response = await fetch('/api/models')
        const data = await response.json()
        setModels(data.models || [])
        if (data.models?.length > 0) {
          setSelectedModel(data.models[0])
        }
      } catch (error) {
        console.error('Error fetching models:', error)
      }
    }
    fetchModels()
  }, [])

  // Auto-scroll to bottom when messages or loading changes
  useEffect(() => {
    if (scrollRef.current) {
      setTimeout(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
      }, 100)
    }
  }, [messages, isLoading])

  const saveMessageToConvex = async (message: Omit<Message, 'id'>) => {
    if (!conversationId) return
    
    try {
      await fetch('/api/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversationId,
          ...message,
        }),
      })
    } catch (error) {
      console.error('Failed to save message:', error)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || !selectedModel) return

    // Create conversation if none exists
    if (!conversationId) {
      await handleNewChat()
      // Wait a moment for the conversation ID to be set
      await new Promise(resolve => setTimeout(resolve, 100))
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // Save user message to Convex
    await saveMessageToConvex(userMessage)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          model: selectedModel,
          messages: [...messages, userMessage],
          conversationId,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to send message')
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let assistantContent = ''

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
      }

      setMessages(prev => [...prev, assistantMessage])

      while (true) {
        const { done, value } = await reader!.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          const trimmedLine = line.trim();
          
          if (trimmedLine.startsWith('data: ')) {
            const dataStr = trimmedLine.replace('data: ', '').trim();
            if (dataStr === '[DONE]') continue;

            try {
              const data = JSON.parse(dataStr);
              const content = data.choices?.[0]?.delta?.content;
              if (content) {
                assistantContent += content;
                assistantMessage.content = assistantContent;
                setMessages(prev => {
                  const newMessages = [...prev]
                  newMessages[newMessages.length - 1] = assistantMessage
                  return newMessages
                });
              }
            } catch (e) {
              // Skip invalid JSON lines
              continue
            }
          }
        }
      }

      // Save complete assistant message to Convex
      await saveMessageToConvex(assistantMessage)

      setIsLoading(false)
    } catch (error) {
      console.error('Error sending message:', error)
      console.error('Error details:', error)
      
      let errorMessageText = 'Sorry, something went wrong. Please try again.'
      if (error instanceof Response) {
        errorMessageText = `Server error: ${error.status} ${error.statusText}`
      } else if (error instanceof Error) {
        errorMessageText = `Error: ${error.message}`
      }
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: errorMessageText,
      }
      setMessages(prev => [...prev, errorMessage])
      await saveMessageToConvex(errorMessage)
      setIsLoading(false)
    }
  }

  const handleNewChat = async () => {
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
    setInput('')
  }

  const handleConversationSelect = async (id: string | null) => {
    setConversationId(id)
    if (id) {
      localStorage.setItem('activeConversationId', id)
    } else {
      localStorage.removeItem('activeConversationId')
    }
    setInput('')
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <Sidebar
        activeConversationId={conversationId}
        onConversationSelect={handleConversationSelect}
        onNewChat={handleNewChat}
        className="w-80"
      />
      
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col max-w-4xl mx-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h1 className="text-2xl font-bold">PyAMA Chat</h1>
          <div className="flex items-center gap-2">
            <label htmlFor="model-select" className="text-sm text-muted-foreground">
              Model:
            </label>
            <select
              id="model-select"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={models.length === 0}
              className="border rounded-md px-2 py-1 text-sm bg-background"
            >
              {models.length === 0 ? (
                <option>Loading...</option>
              ) : (
                models.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))
              )}
            </select>
          </div>
        </div>
        
        <ScrollArea className="flex-1 p-4">
          <div className="space-y-4">
            {messages.length === 0 ? (
              <p className="text-muted-foreground text-center">
                Start a conversation by typing a message below.
              </p>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-2 whitespace-pre-wrap ${
                      message.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted'
                    }`}
                  >
                    {message.content}
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-lg px-4 py-2">
                  <div className="animate-pulse">Thinking...</div>
                </div>
              </div>
            )}
          </div>
          {/* Hidden element to scroll to */}
          <div ref={scrollRef} style={{ height: 1 }} />
        </ScrollArea>

        <form onSubmit={handleSubmit} className="flex gap-2 mt-4 p-4">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading || !selectedModel}
            className="flex-1"
          />
          <Button type="submit" disabled={isLoading || !selectedModel}>
            Send
          </Button>
        </form>
      </div>
    </div>
  )
}
