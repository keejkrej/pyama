import { useState, useEffect } from 'react';
import { cn } from '../../lib/utils';

interface NumberInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'value' | 'onChange'> {
  label?: string;
  value: number;
  onChange?: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  error?: string;
}

export function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  error,
  className,
  ...props
}: NumberInputProps) {
  // Format value based on step
  const formatValue = (val: number): string => {
    if (step < 1) {
      const stepDecimals = step.toString().split('.')[1]?.length || 0;
      return val.toFixed(stepDecimals);
    }
    return val.toString();
  };

  const [localValue, setLocalValue] = useState(formatValue(value));

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.currentTarget.value;
    setLocalValue(newValue);
    const numValue = parseFloat(newValue);
    if (!isNaN(numValue) && onChange) {
      onChange(numValue);
    }
  };

  const handleBlur = () => {
    const numValue = parseFloat(localValue);
    if (isNaN(numValue)) {
      setLocalValue(value.toString());
    } else {
      let clampedValue = numValue;
      if (min !== undefined) clampedValue = Math.max(clampedValue, min);
      if (max !== undefined) clampedValue = Math.min(clampedValue, max);
      setLocalValue(formatValue(clampedValue));
      if (onChange && clampedValue !== value) {
        onChange(clampedValue);
      }
    }
  };

  const increment = () => {
    const newValue = (value || 0) + step;
    const clampedValue = max !== undefined ? Math.min(newValue, max) : newValue;
    if (onChange) onChange(clampedValue);
    setLocalValue(formatValue(clampedValue));
  };

  const decrement = () => {
    const newValue = (value || 0) - step;
    const clampedValue = min !== undefined ? Math.max(newValue, min) : newValue;
    if (onChange) onChange(clampedValue);
    setLocalValue(formatValue(clampedValue));
  };

  // Update localValue when value prop changes
  useEffect(() => {
    setLocalValue(formatValue(value));
  }, [value, step]);

  return (
    <div className={cn(className || 'w-full', 'min-w-0')}>
      {label && (
        <label className="text-xs font-medium leading-tight peer-disabled:cursor-not-allowed peer-disabled:opacity-70 mb-1.5 block text-foreground-bright">
          {label}
        </label>
      )}
      <div className="relative flex items-center rounded-md border border-border bg-[var(--color-input)] overflow-hidden h-8 w-full">
        <input
          type="number"
          value={localValue}
          onChange={handleChange}
          onBlur={handleBlur}
          min={min}
          max={max}
          step={step}
          className={cn(
            'flex h-8 flex-1 bg-transparent px-3 py-1.5 pr-10 text-xs text-foreground placeholder:text-muted-foreground transition-all duration-200 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
            '[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none',
            error && 'border-destructive focus-visible:ring-destructive'
          )}
          {...props}
        />
        <div className="absolute right-0 top-0 bottom-0 flex flex-col border-l border-border">
          <button
            type="button"
            onClick={increment}
            disabled={max !== undefined && value >= max}
            className={cn(
              'flex-1 px-1.5 text-[10px] bg-[var(--color-input)] hover:bg-accent hover:text-accent-foreground text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center border-b border-border',
              'focus-visible:outline-none'
            )}
          >
            ▲
          </button>
          <button
            type="button"
            onClick={decrement}
            disabled={min !== undefined && value <= min}
            className={cn(
              'flex-1 px-1.5 text-[10px] bg-[var(--color-input)] hover:bg-accent hover:text-accent-foreground text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center',
              'focus-visible:outline-none'
            )}
          >
            ▼
          </button>
        </div>
      </div>
      {error && (
        <p className="text-xs font-medium text-destructive mt-1">{error}</p>
      )}
    </div>
  );
}
