import { Link } from 'preact-router/match';
import type { JSX } from 'preact';
import { Settings, Eye, BarChart3 } from 'lucide-preact';
import { cn } from '../../lib/utils';
import { ThemeToggle } from '../ui/theme-toggle';

interface NavLinkProps {
  href: string;
  icon: JSX.Element;
  children: string;
}

function NavLink({ href, icon, children }: NavLinkProps) {
  const linkProps = {
    href,
    class: cn(
      "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200",
      "text-muted-foreground hover:text-foreground hover:bg-accent/50"
    ),
    activeClassName: "bg-accent text-accent-foreground",
  } as JSX.HTMLAttributes<HTMLAnchorElement> & { activeClassName?: string };

  return (
    <Link {...linkProps}>
      <span className="w-3.5 h-3.5 flex-shrink-0">
        {icon}
      </span>
      <span>{children}</span>
    </Link>
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
            <NavLink href="/" icon={<Settings className="w-3.5 h-3.5" />}>
              Processing
            </NavLink>
            <NavLink href="/visualization" icon={<Eye className="w-3.5 h-3.5" />}>
              Visualization
            </NavLink>
            <NavLink href="/analysis" icon={<BarChart3 className="w-3.5 h-3.5" />}>
              Analysis
            </NavLink>
          </div>
        </div>

        <ThemeToggle />
      </div>
    </nav>
  );
}
