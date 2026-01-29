import { cn } from '../../lib/utils';

export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className, ...props }: InputProps) {
  return (
    <div className="w-full">
      {label && (
        <label className="text-xs font-medium leading-tight peer-disabled:cursor-not-allowed peer-disabled:opacity-70 mb-1.5 block text-foreground-bright">
          {label}
        </label>
      )}
      <input
        className={cn(
          'flex h-8 w-full rounded-md border border-border bg-[var(--color-input)] px-3 py-1.5 text-xs text-foreground file:border-0 file:bg-transparent file:text-xs file:font-medium file:text-foreground placeholder:text-muted-foreground transition-all duration-200 focus-visible:outline-none focus-visible:border-foreground/50 disabled:cursor-not-allowed disabled:opacity-50 hover:border-foreground/30',
          error && 'border-destructive focus-visible:ring-destructive',
          className
        )}
        {...props}
      />
      {error && (
        <p className="text-xs font-medium text-destructive mt-1">{error}</p>
      )}
    </div>
  );
}
