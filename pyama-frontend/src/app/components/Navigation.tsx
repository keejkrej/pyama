'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { BackendStatus } from './BackendStatus';

const navItems = [
  { href: '/', label: 'Processing' },
  { href: '/visualization', label: 'Visualization' },
  { href: '/analysis', label: 'Analysis' },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto max-w-[1600px] px-6">
        <div className="flex h-14 items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-lg font-bold text-foreground">PyAMA</span>
            </Link>
            <div className="flex items-center gap-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-muted text-foreground'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <BackendStatus />
          </div>
        </div>
      </div>
    </nav>
  );
}
