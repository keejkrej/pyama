import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';

interface SectionProps {
  title: string;
  children?: ReactNode;
  className?: string;
}

export function Section({ title, children, className }: SectionProps) {
  if (!title) {
    return <div className={cn('space-y-2.5', className)}>{children}</div>;
  }
  return (
    <div className={cn('mb-4', className)}>
      <h2 className="text-xs font-semibold mb-2 uppercase tracking-wider text-foreground-bright">{title}</h2>
      <div className="space-y-2.5">{children}</div>
    </div>
  );
}
