import { cn } from '../../lib/utils';

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'checked'> {
  label?: string;
  checked?: boolean;
}

export function Checkbox({ label, className, ...props }: CheckboxProps) {
  return (
    <div className="flex items-center space-x-2">
      <input
        type="checkbox"
        className={cn(
          'peer h-3.5 w-3.5 shrink-0 rounded-sm border border-border ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 checked:bg-primary checked:border-primary checked:text-primary-foreground transition-all duration-200',
          className
        )}
        {...props}
      />
      {label && (
        <label
          htmlFor={props.id}
          className="text-xs font-medium leading-tight peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer text-foreground"
        >
          {label}
        </label>
      )}
    </div>
  );
}
