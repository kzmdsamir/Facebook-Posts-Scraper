"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { BookOpen, ChevronDown, History, Home, KeyRound, Moon, ScanLine, Settings, Sun } from "lucide-react";
import { DOCS_SECTIONS } from "@/lib/docs-meta";
import { cn } from "@/lib/utils";
import { useTheme } from "@/components/theme-provider";

function NavLink({
  href,
  label,
  icon: Icon,
  onClick,
}: {
  href: string;
  label: string;
  icon: typeof Home;
  onClick?: () => void;
}) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <Link
      href={href}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 px-4 py-2 font-sans text-sm font-light transition-colors",
        active
          ? "border-l-2 border-red-700 text-white pl-3 bg-transparent"
          : "pl-4 text-neutral-400 hover:text-white hover:bg-neutral-800/50",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
      <span>{label}</span>
    </Link>
  );
}

function isDocsPath(pathname: string): boolean {
  return pathname === "/docs" || pathname.startsWith("/docs/");
}

function DocsDropdown({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const isActivePath = isDocsPath(pathname);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (isActivePath) setOpen(true);
  }, [isActivePath]);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((c) => !c)}
        aria-expanded={open}
        className={cn(
          "flex w-full items-center gap-3 px-4 py-2 font-sans text-sm font-light transition-colors",
          isActivePath
            ? "border-l-2 border-red-700 text-white pl-3"
            : "pl-4 text-neutral-400 hover:text-white hover:bg-neutral-800/50",
        )}
      >
        <BookOpen className="h-4 w-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        <span className="flex-1 text-left">Docs</span>
        <ChevronDown
          className={cn("h-3.5 w-3.5 shrink-0 text-neutral-500 transition-transform duration-200", open && "rotate-180")}
          strokeWidth={1.75}
          aria-hidden="true"
        />
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            key="docs-sub"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden bg-neutral-900"
          >
            <div className="py-1">
              {DOCS_SECTIONS.map((section) => (
                <div key={section.title} className="mt-2 first:mt-0">
                  <p className="px-4 pb-1 pt-2 font-sans font-light text-[10px] uppercase tracking-[0.2em] text-neutral-500">
                    {section.title}
                  </p>
                  {section.pages.map((page) => {
                    const href = page.slug === "overview" ? "/docs" : `/docs/${page.slug}`;
                    const active =
                      page.slug === "overview" ? pathname === "/docs" : pathname === `/docs/${page.slug}`;
                    return (
                      <Link
                        key={page.slug}
                        href={href}
                        onClick={onNavigate}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "flex items-center gap-2.5 py-1.5 pl-10 pr-4 font-sans text-sm font-light transition-colors",
                          active ? "text-red-700" : "text-neutral-400 hover:text-white hover:bg-neutral-800/50",
                        )}
                      >
                        <span className={cn("h-1.5 w-1.5 rounded-full", active ? "bg-red-700" : "bg-neutral-700")} aria-hidden="true" />
                        <span className="truncate">{page.title}</span>
                      </Link>
                    );
                  })}
                </div>
              ))}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export function AppSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { theme, toggleTheme } = useTheme();
  const pathname = usePathname();
  const router = useRouter();

  // "Home" and "Investigation" are fresh-slate screens: if the current URL
  // carries piped-in query params (?url= from Home, ?job= from History), strip
  // them even when the path is already correct so each screen resets instead
  // of re-opening a stale run or target.
  const stripPipedParams = (href: string) => {
    if (pathname === href && typeof window !== "undefined") {
      const searchParams = new URLSearchParams(window.location.search);
      if (searchParams.size > 0) router.replace(href);
    }
    onNavigate?.();
  };

  const goHome = () => stripPipedParams("/");
  const goInvestigation = () => stripPipedParams("/investigation");

  return (
    <aside className="flex h-full w-72 flex-col border-r border-neutral-800 bg-black text-white">
      <nav className="flex-1 overflow-y-auto">
        <NavLink href="/" label="Home" icon={Home} onClick={goHome} />
        <NavLink href="/investigation" label="Investigation" icon={ScanLine} onClick={goInvestigation} />
        <NavLink href="/history" label="History" icon={History} onClick={onNavigate} />
        <NavLink href="/accounts" label="Saved accounts" icon={KeyRound} onClick={onNavigate} />
        <DocsDropdown onNavigate={onNavigate} />
        <NavLink href="/settings" label="Settings" icon={Settings} onClick={onNavigate} />
      </nav>

      <div className="border-t border-neutral-800 px-4 py-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2 font-sans font-light text-[11px] uppercase tracking-[0.2em] text-neutral-500">
            <span className="h-1.5 w-1.5 rounded-full bg-red-700 animate-pulse-dot" aria-hidden="true" />
            api :8000
          </span>
          <button
            type="button"
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="flex h-7 w-7 items-center justify-center rounded-none border border-neutral-800 text-neutral-400 transition-colors hover:text-white"
          >
            {theme === "dark" ? (
              <Sun className="h-3.5 w-3.5" strokeWidth={1.75} />
            ) : (
              <Moon className="h-3.5 w-3.5" strokeWidth={1.75} />
            )}
          </button>
        </div>
        <p className="font-sans font-light text-[10px] uppercase tracking-[0.2em] text-neutral-600 tabular-nums">v1.0.0</p>
      </div>
    </aside>
  );
}