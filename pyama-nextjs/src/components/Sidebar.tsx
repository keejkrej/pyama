'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { MessageSquare, Plus, Trash2, Edit2, Check, X } from 'lucide-react'

interface Conversation {
  _id: string
  title: string
  model: string
  createdAt: number
  updatedAt: number
}

interface SidebarProps {
  activeConversationId: string | null
  onConversationSelect: (id: string) => void
  onNewChat: () => void
  className?: string
}

export function Sidebar({ activeConversationId, onConversationSelect, onNewChat, className }: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')

  useEffect(() => {
    loadConversations()
    // Poll for updates every 5 seconds
    const interval = setInterval(loadConversations, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadConversations = async () => {
    try {
      const response = await fetch('/api/conversations')
      const data = await response.json()
      setConversations(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error('Failed to load conversations:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    if (!confirm('Are you sure you want to delete this conversation?')) {
      return
    }

    try {
      await fetch(`/api/conversations/${id}`, {
        method: 'DELETE',
      })
      
      setConversations(prev => prev.filter(conv => conv._id !== id))
      
      if (activeConversationId === id) {
        // Clear active conversation - will be created when user sends first message
        onConversationSelect(null)
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error)
    }
  }

  const handleRenameStart = (id: string, title: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(id)
    setEditingTitle(title)
  }

  const handleRenameSave = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    if (editingTitle.trim() === '') {
      setEditingId(null)
      return
    }

    try {
      const response = await fetch(`/api/conversations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editingTitle.trim() }),
      })

      if (response.ok) {
        setConversations(prev => 
          prev.map(conv => 
            conv._id === id 
              ? { ...conv, title: editingTitle.trim(), updatedAt: Date.now() }
              : conv
          )
        )
      }
    } catch (error) {
      console.error('Failed to rename conversation:', error)
    } finally {
      setEditingId(null)
      setEditingTitle('')
    }
  }

  const handleRenameCancel = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(null)
    setEditingTitle('')
  }

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)
    
    if (diffInHours < 24) {
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    } else if (diffInHours < 24 * 7) {
      return date.toLocaleDateString('en-US', { weekday: 'short' })
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }
  }

  return (
    <div className={`flex flex-col h-full bg-muted/30 border-r ${className}`}>
      {/* Header */}
      <div className="p-4 border-b">
        <Button 
          onClick={onNewChat}
          className="w-full justify-start gap-2"
          variant="outline"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      {/* Conversation List */}
      <ScrollArea className="flex-1 p-2">
        <div className="space-y-1">
          {isLoading ? (
            <div className="text-sm text-muted-foreground text-center py-4">
              Loading conversations...
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-sm text-muted-foreground text-center py-4">
              No conversations yet
            </div>
          ) : (
            conversations.map((conversation) => {
              const isActive = conversation._id === activeConversationId
              const isEditing = conversation._id === editingId
              
              return (
                <div
                  key={conversation._id}
                  className={`
                    group relative rounded-lg p-3 cursor-pointer transition-colors
                    hover:bg-accent/50
                    ${isActive ? 'bg-accent' : ''}
                  `}
                  onClick={() => onConversationSelect(conversation._id)}
                >
                  <div className="flex items-start gap-3">
                    <MessageSquare className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      {isEditing ? (
                        <div className="flex items-center gap-1">
                          <input
                            type="text"
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                handleRenameSave(conversation._id, e as any)
                              } else if (e.key === 'Escape') {
                                handleRenameCancel(e as any)
                              }
                            }}
                            className="flex-1 text-sm bg-background border rounded px-1 py-0.5"
                            autoFocus
                            onClick={(e) => e.stopPropagation()}
                          />
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={(e) => handleRenameSave(conversation._id, e)}
                            className="h-6 w-6 p-0"
                          >
                            <Check className="h-3 w-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={(e) => handleRenameCancel(e)}
                            className="h-6 w-6 p-0"
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      ) : (
                        <>
                          <div className="font-medium text-sm truncate">
                            {conversation.title}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatDate(conversation.updatedAt)}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                  
                  {/* Action buttons */}
                  {!isEditing && (
                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => handleRenameStart(conversation._id, conversation.title, e)}
                        className="h-6 w-6 p-0"
                      >
                        <Edit2 className="h-3 w-3" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => handleDeleteConversation(conversation._id, e)}
                        className="h-6 w-6 p-0 hover:text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
