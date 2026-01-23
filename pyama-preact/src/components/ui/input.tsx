import type { JSX } from 'preact';
import { cn } from '../../lib/utils';

export interface InputProps extends JSX.HTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className, ...props }: InputProps) {
  return (
    <div className="w-full">
      {label && (
        <label className="text-sm font-medium leading-tight peer-disabled:cursor-not-allowed peer-disabled:opacity-70 mb-2 block" style={{ color: 'hsl(0 0% 95%)' }}>
          {label}
        </label>
      )}
      <input
        className={cn(
          'flex h-10 w-full rounded-lg border bg-[var(--color-input)] px-4 py-2 text-sm text-foreground file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground transition-all duration-200 focus-visible:outline-none focus-visible:border-border disabled:cursor-not-allowed disabled:opacity-50 hover:border-foreground/30',
          error && 'border-destructive focus-visible:ring-destructive',
          className
        )}
        style={{ borderColor: 'var(--color-border)' }}
        {...props}
      />
      {error && (
        <p className="text-sm font-medium text-destructive mt-1">{error}</p>
      )}
    </div>
  );
}
