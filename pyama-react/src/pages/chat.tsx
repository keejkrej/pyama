import { ChatContainer, ChatInput, MessageBubble, ToolCallDisplay } from '../components/chat';
import { useChatContext } from '../contexts';

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

export function ChatPage() {
  const { items, isProcessing, error, sendMessage, cancelQuery } = useChatContext();

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border">
        <h1 className="text-lg font-semibold text-foreground-bright">Chat</h1>
        <p className="text-xs text-muted-foreground">
          Ask questions about your microscopy data using natural language
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-5 mt-3 p-3 bg-destructive/10 border border-destructive rounded-md">
          <p className="text-xs text-destructive">{error}</p>
        </div>
      )}

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-h-0">
        <ChatContainer>
          {items.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-xs">
              <div className="text-center space-y-2">
                <p>No messages yet</p>
                <p className="text-muted-foreground/70">
                  Try: "What tools do you have access to?" or "Load /path/to/file.nd2"
                </p>
              </div>
            </div>
          ) : (
            items.map((item) =>
              item.type === 'message' ? (
                <MessageBubble
                  key={(item.data as ChatMessage).id}
                  role={(item.data as ChatMessage).role}
                  content={(item.data as ChatMessage).content}
                />
              ) : (
                <ToolCallDisplay
                  key={(item.data as ToolCall).id}
                  toolName={(item.data as ToolCall).toolName}
                  input={(item.data as ToolCall).input}
                  result={(item.data as ToolCall).result}
                  isError={(item.data as ToolCall).isError}
                  isComplete={(item.data as ToolCall).isComplete}
                />
              )
            )
          )}

          {/* Typing indicator */}
          {isProcessing && items.length > 0 && (() => {
            const lastItem = items[items.length - 1];
            const isLastToolComplete = lastItem?.type === 'tool' && (lastItem.data as ToolCall).isComplete;
            const isLastMessage = lastItem?.type === 'message';
            // Show indicator only if we're waiting for more content
            if (!isLastMessage && !isLastToolComplete) return null;
            return (
              <div className="flex items-center gap-2 text-muted-foreground">
                <span className="w-2 h-2 bg-muted-foreground rounded-full animate-pulse" />
                <span className="text-xs">Thinking...</span>
              </div>
            );
          })()}
        </ChatContainer>

        <ChatInput
          onSend={sendMessage}
          onCancel={cancelQuery}
          isProcessing={isProcessing}
          disabled={!window.agentAPI}
        />
      </div>
    </div>
  );
}
