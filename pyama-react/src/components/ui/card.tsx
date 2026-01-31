import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface CardProps {
  title?: string;
  children?: ReactNode;
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
        "rounded-lg border border-border bg-[var(--color-card)] text-card-foreground transition-all duration-200",
        className,
      )}
    >
      {title && (
        <div
          className={cn(
            "flex flex-col space-y-1 px-4 py-3 border-b border-border",
            headerClassName,
          )}
        >
          <h3 className="text-sm font-semibold leading-tight text-foreground-bright">
            {title}
          </h3>
        </div>
      )}
      <div className={cn("p-4", title ? "pt-3" : "pt-4", bodyClassName)}>
        {children}
      </div>
    </div>
  );
}
