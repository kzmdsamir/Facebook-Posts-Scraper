"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Moon, Sun } from "lucide-react";
import { AppSidebar } from "@/components/app-sidebar";
import { useTheme } from "@/components/theme-provider";
import { cn } from "@/lib/utils";

/**
 * White topbar — flat Jost nav split between Home / Investigation / History:
 * bg-white, border-b neutral-200, links font-sans font-medium text-[11px]
 * uppercase tracking-[0.2em] text-neutral-500 hover:text-black.
 */
function TopBar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  const link = cn(
    "font-sans font-medium text-[11px] uppercase tracking-[0.2em] text-neutral-500 transition-colors hover:cursor-pointer hover:text-black"
  );

  const navItems = [
    { href: "/", label: "Home" },
    { href: "/investigation", label: "Investigation" },
    { href: "/history", label: "History" },
  ] as const;

  return (
    <header className="flex h-16 flex-shrink-0 items-center justify-between border-b border-neutral-200 bg-white px-4 sm:px-8">
      <div className="flex items-center gap-6">
        <button
          type="button"
          onClick={onOpenMenu}
          aria-label="Open navigation"
          className="-ml-1 flex h-8 w-8 items-center justify-center rounded-none border border-neutral-200 text-neutral-500 transition-colors hover:text-black lg:hidden"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path d="M1 3h12M1 7h12M1 11h12" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>

        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(link, pathname === item.href && "text-black")}
          >
            {item.label}
          </Link>
        ))}
      </div>

      <div className="flex items-center gap-5">
        <span className="hidden items-center gap-2 font-sans font-medium text-[11px] uppercase tracking-[0.2em] text-neutral-500 sm:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-red-700 animate-pulse-dot" aria-hidden="true" />
          api :8000
        </span>
        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="flex h-8 w-8 items-center justify-center rounded-none border border-neutral-200 text-neutral-500 transition-colors hover:text-black"
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4" strokeWidth={1.75} />
          ) : (
            <Moon className="h-4 w-4" strokeWidth={1.75} />
          )}
        </button>
      </div>
    </header>
  );
}

/**
 * Root shell — MailAccess macro layout: locked viewport, black sidebar rail on
 * the left, white scrollable mail area on the right.
 */
export default function AppShellLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-black font-sans text-black antialiased">
      <aside className="hidden flex-shrink-0 lg:block">
        <AppSidebar />
      </aside>

      {/* Mobile slide-over menu */}
      {mounted && menuOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-black/60"
            onClick={() => setMenuOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 z-10 animate-slide-in-left">
            <AppSidebar onNavigate={() => setMenuOpen(false)} />
          </div>
        </div>
      ) : null}

      <main className="flex min-w-0 flex-1 flex-col overflow-y-auto bg-white">
        <TopBar onOpenMenu={() => setMenuOpen(true)} />
        <div className="mx-auto w-full max-w-7xl flex-1">
          <div className="px-4 py-8 sm:px-8">{children}</div>
        </div>
      </main>
    </div>
  );
}