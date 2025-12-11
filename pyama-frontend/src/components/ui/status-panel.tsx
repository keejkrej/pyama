import { cn } from '@/lib/utils';

interface StatusPanelProps {
  statusMessage: string;
  className?: string;
}

export function StatusPanel({ statusMessage, className }: StatusPanelProps) {
  return (
    <div
      className={cn(
        'flex-1 max-w-md rounded-xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground shadow-sm',
        className
      )}
    >
      <p className="font-semibold text-foreground">Status</p>
      <p
        className="text-xs text-muted-foreground truncate"
        title={statusMessage}
      >
        {statusMessage}
      </p>
    </div>
  );
}
