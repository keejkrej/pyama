import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import type { AgentMessage } from '../../electron/preload';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface ToolCall {
  id: string;
  toolName: string;
  input?: unknown;
  result?: unknown;
  isError?: boolean;
  isComplete: boolean;
}

interface ConversationItem {
  type: 'message' | 'tool';
  data: ChatMessage | ToolCall;
}

interface ChatContextValue {
  items: ConversationItem[];
  isProcessing: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  cancelQuery: () => Promise<void>;
  clearChat: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function useChatContext() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ConversationItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingTools, setPendingTools] = useState<Map<string, ToolCall>>(new Map());

  // Set up message listener once at app level
  useEffect(() => {
    if (!window.agentAPI) return;

    const cleanupMessage = window.agentAPI.onMessage((message: AgentMessage) => {
      handleAgentMessage(message);
    });

    const cleanupDone = window.agentAPI.onDone(() => {
      setIsProcessing(false);
    });

    return () => {
      cleanupMessage();
      cleanupDone();
    };
  }, []);

  const handleAgentMessage = useCallback((message: AgentMessage) => {
    switch (message.type) {
      case 'assistant':
        if (message.content) {
          setItems((prev) => {
            const lastItem = prev[prev.length - 1];
            if (lastItem?.type === 'message' && (lastItem.data as ChatMessage).role === 'assistant') {
              // Append to existing message
              return prev.map((item, i) =>
                i === prev.length - 1
                  ? {
                      ...item,
                      data: {
                        ...(item.data as ChatMessage),
                        content: (item.data as ChatMessage).content + message.content,
                      },
                    }
                  : item
              );
            } else {
              // Create new assistant message
              return [
                ...prev,
                {
                  type: 'message',
                  data: {
                    id: crypto.randomUUID(),
                    role: 'assistant',
                    content: message.content || '',
                  },
                },
              ];
            }
          });
        }
        break;

      case 'tool_use':
        if (message.toolName) {
          const toolId = crypto.randomUUID();
          const toolCall: ToolCall = {
            id: toolId,
            toolName: message.toolName,
            input: message.toolInput,
            isComplete: false,
          };
          setPendingTools((prev) => new Map(prev).set(message.toolName!, toolCall));
          setItems((prev) => [...prev, { type: 'tool', data: toolCall }]);
        }
        break;

      case 'tool_result':
        setPendingTools((prev) => {
          const updated = new Map(prev);
          for (const [key, tool] of updated) {
            if (!tool.isComplete) {
              const completedTool: ToolCall = {
                ...tool,
                result: message.toolResult,
                isError: message.isError,
                isComplete: true,
              };
              setItems((prevItems) =>
                prevItems.map((item) =>
                  item.type === 'tool' && (item.data as ToolCall).id === tool.id
                    ? { ...item, data: completedTool }
                    : item
                )
              );
              updated.delete(key);
              break;
            }
          }
          return updated;
        });
        break;

      case 'error':
        setError(message.content || 'An error occurred');
        setIsProcessing(false);
        break;
    }
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (!window.agentAPI) {
      setError('Agent API not available');
      return;
    }

    setError(null);
    setIsProcessing(true);

    // Add user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
    };
    setItems((prev) => [...prev, { type: 'message', data: userMessage }]);

    try {
      await window.agentAPI.query(content);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Query failed');
      setIsProcessing(false);
    }
  }, []);

  const cancelQuery = useCallback(async () => {
    if (window.agentAPI) {
      await window.agentAPI.cancel();
    }
    setIsProcessing(false);
  }, []);

  const clearChat = useCallback(() => {
    setItems([]);
    setError(null);
    setPendingTools(new Map());
  }, []);

  return (
    <ChatContext.Provider
      value={{
        items,
        isProcessing,
        error,
        sendMessage,
        cancelQuery,
        clearChat,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}
