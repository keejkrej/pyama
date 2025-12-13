import { cn } from '@/lib/utils';

interface PanelProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  description?: string;
}

export function Panel({ children, className, title, description }: PanelProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-card p-6 shadow-sm space-y-4',
        className
      )}
    >
      {(title || description) && (
        <div className="space-y-1">
          {title && (
            <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          )}
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

interface SectionProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  description?: string;
}

export function Section({
  children,
  className,
  title,
  description,
}: SectionProps) {
  return (
    <section
      className={cn(
        'rounded-xl border border-border bg-card p-6 shadow-sm space-y-6',
        className
      )}
    >
      {(title || description) && (
        <div className="space-y-1">
          {title && (
            <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          )}
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  );
}
