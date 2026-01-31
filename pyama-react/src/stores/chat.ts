import { create } from "zustand";
import type { AgentMessage } from "../../electron/preload";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
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
  type: "message" | "tool";
  data: ChatMessage | ToolCall;
}

interface ChatState {
  items: ConversationItem[];
  isProcessing: boolean;
  error: string | null;
  pendingTools: Map<string, ToolCall>;

  // Actions
  handleAgentMessage: (message: AgentMessage) => void;
  setIsProcessing: (processing: boolean) => void;
  setError: (error: string | null) => void;
  sendMessage: (content: string) => Promise<void>;
  cancelQuery: () => Promise<void>;
  clearChat: () => void;
}

export const useChatStore = create<ChatState>()((set, get) => ({
  items: [],
  isProcessing: false,
  error: null,
  pendingTools: new Map(),

  handleAgentMessage: (message: AgentMessage) => {
    switch (message.type) {
      case "assistant":
        if (message.content) {
          set((state) => {
            const lastItem = state.items[state.items.length - 1];
            if (
              lastItem?.type === "message" &&
              (lastItem.data as ChatMessage).role === "assistant"
            ) {
              // Append to existing message
              return {
                items: state.items.map((item, i) =>
                  i === state.items.length - 1
                    ? {
                        ...item,
                        data: {
                          ...(item.data as ChatMessage),
                          content:
                            (item.data as ChatMessage).content + message.content,
                        },
                      }
                    : item
                ),
              };
            } else {
              // Create new assistant message
              return {
                items: [
                  ...state.items,
                  {
                    type: "message" as const,
                    data: {
                      id: crypto.randomUUID(),
                      role: "assistant" as const,
                      content: message.content || "",
                    },
                  },
                ],
              };
            }
          });
        }
        break;

      case "tool_use":
        if (message.toolName) {
          const toolId = crypto.randomUUID();
          const toolCall: ToolCall = {
            id: toolId,
            toolName: message.toolName,
            input: message.toolInput,
            isComplete: false,
          };
          set((state) => {
            const newPendingTools = new Map(state.pendingTools);
            newPendingTools.set(message.toolName!, toolCall);
            return {
              pendingTools: newPendingTools,
              items: [...state.items, { type: "tool" as const, data: toolCall }],
            };
          });
        }
        break;

      case "tool_result":
        set((state) => {
          const newPendingTools = new Map(state.pendingTools);
          let newItems = state.items;

          for (const [key, tool] of newPendingTools) {
            if (!tool.isComplete) {
              const completedTool: ToolCall = {
                ...tool,
                result: message.toolResult,
                isError: message.isError,
                isComplete: true,
              };
              newItems = newItems.map((item) =>
                item.type === "tool" && (item.data as ToolCall).id === tool.id
                  ? { ...item, data: completedTool }
                  : item
              );
              newPendingTools.delete(key);
              break;
            }
          }

          return { pendingTools: newPendingTools, items: newItems };
        });
        break;

      case "error":
        set({
          error: message.content || "An error occurred",
          isProcessing: false,
        });
        break;
    }
  },

  setIsProcessing: (processing) => set({ isProcessing: processing }),
  setError: (error) => set({ error }),

  sendMessage: async (content: string) => {
    if (!window.agentAPI) {
      set({ error: "Agent API not available" });
      return;
    }

    set({ error: null, isProcessing: true });

    // Add user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
    };
    set((state) => ({
      items: [...state.items, { type: "message" as const, data: userMessage }],
    }));

    try {
      await window.agentAPI.query(content);
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Query failed",
        isProcessing: false,
      });
    }
  },

  cancelQuery: async () => {
    if (window.agentAPI) {
      await window.agentAPI.cancel();
    }
    set({ isProcessing: false });
  },

  clearChat: () => {
    set({
      items: [],
      error: null,
      pendingTools: new Map(),
    });
  },
}));

// Types exported for use in components
export type { ChatMessage, ToolCall, ConversationItem };
