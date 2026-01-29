import { useState, useRef, useEffect } from 'react';
import { Send, Square } from 'lucide-react';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';

interface ChatInputProps {
  onSend: (message: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
  isProcessing?: boolean;
}

export function ChatInput({ onSend, onCancel, disabled, isProcessing }: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (trimmed && !disabled && !isProcessing) {
      onSend(trimmed);
      setValue('');
      // Reset height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex items-end gap-2 p-3 border-t border-border bg-[var(--color-card)]">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about your microscopy data..."
        disabled={disabled}
        rows={1}
        className={cn(
          'flex-1 resize-none rounded-md border border-border bg-[var(--color-input)] px-3 py-2',
          'text-xs text-foreground placeholder:text-muted-foreground',
          'focus:outline-none focus:border-foreground/50 transition-colors',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'min-h-[36px] max-h-[150px]'
        )}
      />
      {isProcessing ? (
        <Button
          variant="destructive"
          size="icon"
          onClick={onCancel}
          className="h-9 w-9 shrink-0"
        >
          <Square className="w-4 h-4" />
        </Button>
      ) : (
        <Button
          variant="default"
          size="icon"
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          className="h-9 w-9 shrink-0"
        >
          <Send className="w-4 h-4" />
        </Button>
      )}
    </div>
  );
}
