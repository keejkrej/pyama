import { Link } from 'preact-router/match';
import type { JSX } from 'preact';

interface NavLinkProps {
  href: string;
  children: string;
}

function NavLink({ href, children }: NavLinkProps) {
  // preact-router/match Link types are incomplete - href is valid at runtime
  const linkProps = {
    href,
    class: "px-4 py-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors",
    activeClassName: "bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 font-medium",
  } as JSX.HTMLAttributes<HTMLAnchorElement> & { activeClassName?: string };

  return (
    <Link {...linkProps}>
      {children}
    </Link>
  );
}

export function Navbar() {
  return (
    <nav className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-4 py-2">
      <div className="flex items-center justify-between max-w-7xl mx-auto">
        {/* Logo */}
        <div className="flex items-center gap-2">
          <span className="text-xl font-bold text-blue-600 dark:text-blue-400">PyAMA</span>
        </div>

        {/* Navigation Links */}
        <div className="flex items-center gap-1">
          <NavLink href="/">Processing</NavLink>
          <NavLink href="/visualization">Visualization</NavLink>
          <NavLink href="/analysis">Analysis</NavLink>
        </div>

        {/* Placeholder for future actions */}
        <div className="w-20" />
      </div>
    </nav>
  );
}
