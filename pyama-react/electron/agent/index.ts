import { query, type SDKMessage } from "@anthropic-ai/claude-agent-sdk";

const PYAMA_SYSTEM_PROMPT = `You are PyAMA Assistant, helping users analyze microscopy images.

Available tools via MCP:
- load_microscopy: Load ND2/CZI/TIFF files and get metadata
- create_processing_task: Start image processing with given config
- list_tasks: Show all processing tasks
- get_task: Get status/progress of a specific task
- cancel_task: Cancel a running task

When users ask to process files, use these tools. Explain what you're doing.`;

export interface AgentMessage {
  type: "assistant" | "tool_use" | "tool_result" | "result" | "error";
  content?: string;
  toolName?: string;
  toolInput?: unknown;
  toolResult?: unknown;
  isError?: boolean;
}

/**
 * Runs a query through the Claude Agent SDK with isolated MCP configuration.
 * Only connects to pyama MCP server - ignores user's ~/.claude/ config.
 */
export async function* agentQuery(
  prompt: string,
): AsyncGenerator<AgentMessage> {
  try {
    for await (const message of query({
      prompt,
      options: {
        // Isolated MCP config - only pyama, ignores user's personal MCP configs
        mcpServers: {
          pyama: {
            type: "http",
            url: "http://localhost:8765/mcp",
          },
        },
        // Only allow pyama MCP tools - no filesystem access (Read, Write, Bash, etc.)
        allowedTools: ["mcp__pyama__*"],
        model: "claude-haiku-4-5",
        systemPrompt: PYAMA_SYSTEM_PROMPT,
      },
    })) {
      // Convert SDK messages to our simplified format
      yield* processMessage(message);
    }
  } catch (error) {
    yield {
      type: "error",
      content:
        error instanceof Error ? error.message : "Unknown error occurred",
      isError: true,
    };
  }
}

function* processMessage(message: SDKMessage): Generator<AgentMessage> {
  if (message.type === "assistant") {
    // SDKAssistantMessage has a `message` property containing the API response
    const assistantMsg = message as {
      type: "assistant";
      message: { content: unknown };
    };
    const content = assistantMsg.message?.content;

    if (typeof content === "string") {
      yield { type: "assistant", content };
    } else if (Array.isArray(content)) {
      for (const block of content) {
        if (typeof block === "object" && block !== null) {
          const typedBlock = block as {
            type: string;
            text?: string;
            name?: string;
            input?: unknown;
          };
          if (typedBlock.type === "text" && typedBlock.text) {
            yield { type: "assistant", content: typedBlock.text };
          } else if (typedBlock.type === "tool_use" && typedBlock.name) {
            yield {
              type: "tool_use",
              toolName: typedBlock.name,
              toolInput: typedBlock.input,
            };
          }
        }
      }
    }
  } else if (message.type === "result") {
    // SDKResultMessage - final result
    const resultMsg = message as {
      type: "result";
      subtype: string;
      result?: string;
      is_error?: boolean;
    };
    yield {
      type: "result",
      content: resultMsg.result || "Query completed",
      isError: resultMsg.is_error,
    };
  }
  // Note: Tool results are handled internally by the SDK's agentic loop
}
