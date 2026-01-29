import { cn } from '../../lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

interface MessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
}

const markdownComponents: Components = {
  // Style code blocks
  pre: ({ children }) => (
    <pre className="bg-[var(--color-input)] rounded-md p-3 overflow-x-auto my-2 text-xs">
      {children}
    </pre>
  ),
  code: ({ className, children, ...props }) => {
    const isInline = !className;
    return isInline ? (
      <code className="bg-[var(--color-input)] px-1 py-0.5 rounded text-xs" {...props}>
        {children}
      </code>
    ) : (
      <code className={cn("text-xs", className)} {...props}>
        {children}
      </code>
    );
  },
  // Style links
  a: ({ href, children }) => (
    <a href={href} className="text-info hover:underline" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  // Style lists
  ul: ({ children }) => (
    <ul className="list-disc list-inside my-2 space-y-1">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside my-2 space-y-1">
      {children}
    </ol>
  ),
  // Style tables
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full border border-border rounded">
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-border px-2 py-1 bg-[var(--color-input)] text-left text-xs font-medium">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-border px-2 py-1 text-xs">
      {children}
    </td>
  ),
  // Style paragraphs
  p: ({ children }) => (
    <p className="my-1.5 leading-relaxed">
      {children}
    </p>
  ),
  // Style headers
  h1: ({ children }) => <h1 className="text-lg font-semibold mt-3 mb-2">{children}</h1>,
  h2: ({ children }) => <h2 className="text-base font-semibold mt-2.5 mb-1.5">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
};

export function MessageBubble({ role, content }: MessageBubbleProps) {
  const isUser = role === 'user';

  return (
    <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-lg px-3 py-2 text-xs',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-[var(--color-card)] border border-border text-foreground'
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="prose-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
