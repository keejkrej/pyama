import type { ComponentChildren } from 'preact';
import { cn } from '../../lib/utils';

interface SectionProps {
  title: string;
  children?: ComponentChildren;
  className?: string;
}

export function Section({ title, children, className }: SectionProps) {
  if (!title) {
    return <div className={cn('space-y-4', className)}>{children}</div>;
  }
  return (
    <div className={cn('mb-6', className)}>
      <h2 className="text-sm font-semibold mb-3 uppercase tracking-wider" style={{ color: 'hsl(0 0% 95%)' }}>{title}</h2>
      <div className="space-y-4">{children}</div>
    </div>
  );
}
