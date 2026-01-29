import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';

interface TableProps {
  children: ReactNode;
  className?: string;
}

interface TableHeaderProps {
  children: ReactNode;
  className?: string;
}

interface TableRowProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}

interface TableCellProps {
  children: ReactNode;
  className?: string;
  header?: boolean;
  colSpan?: number;
}

export function Table({ children, className }: TableProps) {
  return (
    <div className="relative w-full overflow-auto rounded-md border border-border bg-card">
      <table className={cn('w-full caption-bottom text-xs', className)}>
        {children}
      </table>
    </div>
  );
}

export function TableHeader({ children, className }: TableHeaderProps) {
  return <thead className={cn('[&_tr]:border-b border-border', className)}>{children}</thead>;
}

export function TableRow({ children, className, onClick }: TableRowProps) {
  return (
    <tr
      className={cn(
        'border-b border-border transition-colors hover:bg-accent/30 data-[state=selected]:bg-accent',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      {children}
    </tr>
  );
}

export function TableCell({
  children,
  className,
  header = false,
  colSpan,
}: TableCellProps) {
  const Component = header ? 'th' : 'td';
  return (
    <Component
      colSpan={colSpan}
      className={cn(
        header
          ? 'h-9 px-3 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0'
          : 'p-3 align-middle [&:has([role=checkbox])]:pr-0',
        className
      )}
    >
      {children}
    </Component>
  );
}
