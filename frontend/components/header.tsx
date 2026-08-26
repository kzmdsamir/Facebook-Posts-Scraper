"use client";

import { useState } from "react";
import { BookOpen, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/theme-provider";
import { DocsDialog } from "@/components/docs-dialog";

export function Header() {
  const { theme, toggleTheme } = useTheme();
  const [docsOpen, setDocsOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center gap-3 px-4 sm:gap-4 sm:px-6">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.svg" alt="Facebook Posts Scraper logo" className="h-9 w-9 shrink-0 rounded-lg shadow-sm" />
        <div className="min-w-0">
          <p className="truncate text-base font-semibold leading-tight tracking-tight">Facebook Posts Scraper</p>
          <p className="hidden truncate text-xs text-muted-foreground sm:block">
            Public posts · progress tracking · JSON / CSV / Excel export
          </p>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDocsOpen(true)}
            aria-label="Open documentation and compliance help"
          >
            <BookOpen className="h-4 w-4" aria-hidden="true" />
            <span className="hidden md:inline">Documentation</span>
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          >
            {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
          </Button>
        </div>
      </div>

      <DocsDialog open={docsOpen} onClose={() => setDocsOpen(false)} />
    </header>
  );
}