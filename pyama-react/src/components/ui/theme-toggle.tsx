import { Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "../../lib/theme";
import { cn } from "../../lib/utils";

export function ThemeToggle() {
  const { preference, setPreference } = useTheme();

  return (
    <div className="flex items-center gap-0.5 rounded-md border border-border bg-background p-0.5">
      <button
        type="button"
        onClick={() => setPreference("light")}
        className={cn(
          "flex h-6 w-6 items-center justify-center rounded transition-all duration-200",
          preference === "light"
            ? "bg-accent text-accent-foreground"
            : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
        )}
        title="Light mode"
      >
        <Sun className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        onClick={() => setPreference("dark")}
        className={cn(
          "flex h-6 w-6 items-center justify-center rounded transition-all duration-200",
          preference === "dark"
            ? "bg-accent text-accent-foreground"
            : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
        )}
        title="Dark mode"
      >
        <Moon className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        onClick={() => setPreference("system")}
        className={cn(
          "flex h-6 w-6 items-center justify-center rounded transition-all duration-200",
          preference === "system"
            ? "bg-accent text-accent-foreground"
            : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
        )}
        title="Follow system"
      >
        <Monitor className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
