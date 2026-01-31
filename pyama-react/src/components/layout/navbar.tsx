import { NavLink as RouterNavLink } from "react-router-dom";
import type { ReactNode } from "react";
import { Settings, Eye, BarChart3, MessageCircle } from "lucide-react";
import { cn } from "../../lib/utils";
import { ThemeToggle } from "../ui/theme-toggle";

interface NavLinkProps {
  to: string;
  icon: ReactNode;
  children: string;
}

function NavLink({ to, icon, children }: NavLinkProps) {
  return (
    <RouterNavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200",
          "text-muted-foreground hover:text-foreground hover:bg-accent/50",
          isActive && "bg-accent text-accent-foreground",
        )
      }
    >
      <span className="w-3.5 h-3.5 flex-shrink-0">{icon}</span>
      <span>{children}</span>
    </RouterNavLink>
  );
}

export function Navbar() {
  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-background px-5 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <span className="whitespace-nowrap leading-none text-foreground-bright text-xl font-bold tracking-[0.08em]">
            PyAMA
          </span>

          <div className="flex items-center gap-0.5">
            <NavLink to="/" icon={<Settings className="w-3.5 h-3.5" />}>
              Processing
            </NavLink>
            <NavLink to="/visualization" icon={<Eye className="w-3.5 h-3.5" />}>
              Visualization
            </NavLink>
            <NavLink
              to="/analysis"
              icon={<BarChart3 className="w-3.5 h-3.5" />}
            >
              Analysis
            </NavLink>
            <NavLink
              to="/chat"
              icon={<MessageCircle className="w-3.5 h-3.5" />}
            >
              Chat
            </NavLink>
          </div>
        </div>

        <ThemeToggle />
      </div>
    </nav>
  );
}
