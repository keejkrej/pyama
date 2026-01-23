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
      "flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 group",
      "text-muted-foreground hover:text-foreground hover:bg-accent/50"
    ),
    activeClassName: "bg-accent text-accent-foreground",
  } as JSX.HTMLAttributes<HTMLAnchorElement> & { activeClassName?: string };

  return (
    <Link {...linkProps}>
      <span className="w-5 h-5 flex-shrink-0">
        {icon}
      </span>
      <span>{children}</span>
    </Link>
  );
}

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-[var(--color-sidebar)] border-r border-border flex flex-col z-50">
      {/* Logo/Brand Section */}
      <div className="px-6 py-5 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-foreground">PyAMA</span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-4 py-6 space-y-1">
        <NavLink href="/" icon={<Settings className="w-5 h-5" />}>
          Processing
        </NavLink>
        <NavLink href="/visualization" icon={<Eye className="w-5 h-5" />}>
          Visualization
        </NavLink>
        <NavLink href="/analysis" icon={<BarChart3 className="w-5 h-5" />}>
          Analysis
        </NavLink>
      </nav>
    </aside>
  );
}
