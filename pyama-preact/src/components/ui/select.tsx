import type { JSX } from 'preact';
import { cn } from '../../lib/utils';

interface SelectOption {
  value: string | number;
  label: string;
}

export interface SelectProps extends Omit<JSX.HTMLAttributes<HTMLSelectElement>, 'value' | 'onChange'> {
  label?: string;
  options: SelectOption[];
  error?: string;
  value?: string | number;
  onChange?: (e: JSX.TargetedEvent<HTMLSelectElement>) => void;
}

export function Select({ label, options, error, className, value, onChange, ...props }: SelectProps) {
  return (
    <div className="w-full">
      {label && (
        <label className="text-sm font-medium leading-tight peer-disabled:cursor-not-allowed peer-disabled:opacity-70 mb-2 block text-foreground">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          className={cn(
            'flex h-10 w-full items-center justify-between rounded-lg border border-input bg-[var(--color-input)] px-4 py-2 text-sm text-foreground placeholder:text-muted-foreground transition-all duration-200 focus:outline-none focus:border-border disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1 appearance-none pr-8 hover:border-foreground/30',
            error && 'border-destructive focus:ring-destructive',
            className
          )}
          value={value}
          onChange={onChange}
          {...props}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
          <svg
            className="h-4 w-4 opacity-50"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </div>
      {error && (
        <p className="text-sm font-medium text-destructive mt-1">{error}</p>
      )}
    </div>
  );
}
