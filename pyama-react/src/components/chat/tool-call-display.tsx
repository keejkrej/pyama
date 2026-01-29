import { useState } from 'react';
import { ChevronDown, ChevronRight, Wrench, CheckCircle, XCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

interface ToolCallDisplayProps {
  toolName: string;
  input?: unknown;
  result?: unknown;
  isError?: boolean;
  isComplete: boolean;
}

export function ToolCallDisplay({
  toolName,
  input,
  result,
  isError,
  isComplete,
}: ToolCallDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Extract the actual tool name (remove mcp__pyama__ prefix)
  const displayName = toolName.replace(/^mcp__pyama__/, '');

  return (
    <div className="my-2 rounded-md border border-border bg-[var(--color-card)] overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent/30 transition-colors"
      >
        <span className="text-muted-foreground">
          {isExpanded ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </span>
        <Wrench className="w-3.5 h-3.5 text-info" />
        <span className="text-xs font-medium text-foreground flex-1 text-left">
          {displayName}
        </span>
        {isComplete && (
          isError ? (
            <XCircle className="w-3.5 h-3.5 text-destructive" />
          ) : (
            <CheckCircle className="w-3.5 h-3.5 text-success" />
          )
        )}
        {!isComplete && (
          <span className="w-3 h-3 border-2 border-info border-t-transparent rounded-full animate-spin" />
        )}
      </button>

      {isExpanded && (
        <div className="border-t border-border px-3 py-2 space-y-2 text-xs">
          {input && (
            <div>
              <span className="text-muted-foreground font-medium">Input:</span>
              <pre className="mt-1 p-2 bg-[var(--color-input)] rounded text-xs overflow-x-auto">
                {JSON.stringify(input, null, 2)}
              </pre>
            </div>
          )}
          {result && (
            <div>
              <span className={cn(
                "font-medium",
                isError ? "text-destructive" : "text-muted-foreground"
              )}>
                {isError ? "Error:" : "Result:"}
              </span>
              <pre className={cn(
                "mt-1 p-2 rounded text-xs overflow-x-auto max-h-48",
                isError ? "bg-destructive/10 text-destructive" : "bg-[var(--color-input)]"
              )}>
                {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
