import { useRef, useEffect } from 'react';
import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';

interface ChatContainerProps {
  children: ReactNode;
  className?: string;
}

export function ChatContainer({ children, className }: ChatContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);

  // Auto-scroll to bottom when new content is added
  useEffect(() => {
    const container = containerRef.current;
    if (container && shouldAutoScroll.current) {
      container.scrollTop = container.scrollHeight;
    }
  });

  // Track if user has scrolled up
  const handleScroll = () => {
    const container = containerRef.current;
    if (container) {
      const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 50;
      shouldAutoScroll.current = isAtBottom;
    }
  };

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className={cn(
        'flex-1 overflow-y-auto p-4 space-y-3',
        className
      )}
    >
      {children}
    </div>
  );
}
