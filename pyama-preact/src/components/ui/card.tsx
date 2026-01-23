import type { ComponentChildren } from 'preact';
import { cn } from '../../lib/utils';

interface CardProps {
  title?: string;
  children?: ComponentChildren;
  className?: string;
  headerClassName?: string;
  bodyClassName?: string;
}

export function Card({
  title,
  children,
  className,
  headerClassName,
  bodyClassName,
}: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border text-card-foreground transition-all duration-200',
        className
      )}
      style={{ backgroundColor: 'var(--color-card)' }}
    >
      {title && (
        <div
          className={cn(
            'flex flex-col space-y-1.5 px-6 py-5 border-b border-border',
            headerClassName
          )}
        >
          <h3 className="text-lg font-semibold leading-tight" style={{ color: 'hsl(0 0% 95%)' }}>
            {title}
          </h3>
        </div>
      )}
      <div className={cn('p-6', title ? 'pt-5' : 'pt-6', bodyClassName)}>{children}</div>
    </div>
  );
}
