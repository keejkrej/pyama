import { Link } from 'preact-router/match';
import type { JSX } from 'preact';
import { Settings, Eye, BarChart3 } from 'lucide-preact';
import { cn } from '../../lib/utils';

interface NavLinkProps {
  href: string;
  icon: JSX.Element;
  children: string;
}

function NavLink({ href, icon, children }: NavLinkProps) {
  const linkProps = {
    href,
    class: cn(
      "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200",
      "text-muted-foreground hover:text-foreground hover:bg-accent/50"
    ),
    activeClassName: "bg-accent text-accent-foreground",
  } as JSX.HTMLAttributes<HTMLAnchorElement> & { activeClassName?: string };

  return (
    <Link {...linkProps}>
      <span className="w-4 h-4 flex-shrink-0">
        {icon}
      </span>
      <span>{children}</span>
    </Link>
  );
}

export function Navbar() {
  return (
    <nav className="border-b border-border bg-background px-6 py-5">
      <div className="flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3 pr-8 overflow-visible">
          <span
            className="whitespace-nowrap leading-none"
            style={{
              fontFamily: "'Jost', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
              letterSpacing: '0.08em',
              fontWeight: 700,
              fontSize: '2rem',
              lineHeight: '1',
              color: 'hsl(0 0% 95%)',
              display: 'inline-block'
            }}
          >
            PyAMA
          </span>
        </div>

        {/* Navigation Links */}
        <div className="flex items-center gap-1">
          <NavLink href="/" icon={<Settings className="w-4 h-4" />}>
            Processing
          </NavLink>
          <NavLink href="/visualization" icon={<Eye className="w-4 h-4" />}>
            Visualization
          </NavLink>
          <NavLink href="/analysis" icon={<BarChart3 className="w-4 h-4" />}>
            Analysis
          </NavLink>
        </div>

        {/* Placeholder for future actions */}
        <div className="w-20" />
      </div>
    </nav>
  );
}
