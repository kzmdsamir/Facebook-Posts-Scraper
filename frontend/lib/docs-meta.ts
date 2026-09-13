/**
 * Docs registry (client-safe, no JSX) — powers the sidebar Docs dropdown and
 * the /docs routes. Bodies live in app/(app)/docs/content.tsx.
 */
export type DocsIconName =
  | "book"
  | "rocket"
  | "terminal"
  | "globe"
  | "key"
  | "sliders"
  | "database"
  | "download"
  | "shield"
  | "socket"
  | "activity"
  | "table"
  | "box"
  | "alert";

export interface DocsPage {
  slug: string;
  title: string;
  description: string;
  icon: DocsIconName;
}

export interface DocsSection {
  title: string;
  pages: DocsPage[];
}

export const DOCS_SECTIONS: DocsSection[] = [
  {
    title: "Getting started",
    pages: [
      {
        slug: "overview",
        title: "Overview",
        description: "What the scraper does, what it never does, and the big picture.",
        icon: "book",
      },
      {
        slug: "getting-started",
        title: "Getting started",
        description: "Prerequisites, install, and the working directory layout.",
        icon: "rocket",
      },
      {
        slug: "quickstart",
        title: "Quickstart",
        description: "Your first scrape in under five minutes.",
        icon: "activity",
      },
    ],
  },
  {
    title: "Guide",
    pages: [
      {
        slug: "cli",
        title: "Command line",
        description: "Every CLI command, flag and exit code.",
        icon: "terminal",
      },
      {
        slug: "browser-mode",
        title: "Browser mode",
        description: "Playwright-based scraping of the live GraphQL feed.",
        icon: "globe",
      },
      {
        slug: "graphql",
        title: "Why and how: GraphQL",
        description: "The anonymous-HTML wall, the page's own Comet feed, and how the browser captures it.",
        icon: "activity",
      },
      {
        slug: "sessions",
        title: "Sessions & cookies",
        description: "Saved login sessions and Facebook's anonymous cap.",
        icon: "key",
      },
      {
        slug: "options",
        title: "Filters & options",
        description: "Time frames, post types, caps and scroll rounds.",
        icon: "sliders",
      },
      {
        slug: "data",
        title: "Data & dedup",
        description: "The normalized post model and duplicate handling.",
        icon: "database",
      },
      {
        slug: "quirks",
        title: "Facebook quirks & data honesty",
        description: "How the parser stays honest: timestamps, counts, media and markup drift.",
        icon: "alert",
      },
      {
        slug: "exports",
        title: "Exports",
        description: "JSON, CSV and Excel generation, streaming and limits.",
        icon: "download",
      },
      {
        slug: "rate-limits",
        title: "Rate limits & compliance",
        description: "Throttling, safety defaults and responsible use.",
        icon: "shield",
      },
    ],
  },
  {
    title: "API reference",
    pages: [
      {
        slug: "api-scrape",
        title: "POST /api/scrape",
        description: "Start a new scraping job.",
        icon: "socket",
      },
      {
        slug: "api-jobs",
        title: "Jobs & progress",
        description: "Status, pause/resume, delete and history.",
        icon: "activity",
      },
      {
        slug: "api-posts",
        title: "Posts & stats",
        description: "Paginated posts and aggregated KPIs.",
        icon: "table",
      },
      {
        slug: "api-exports",
        title: "Exports & accounts",
        description: "File downloads and saved-session metadata.",
        icon: "box",
      },
      {
        slug: "errors",
        title: "Errors & troubleshooting",
        description: "The error envelope and common failure modes.",
        icon: "alert",
      },
    ],
  },
];

export const DOCS_PAGES: DocsPage[] = DOCS_SECTIONS.flatMap((section) => section.pages);

export function findDocsPage(slug: string): DocsPage | undefined {
  return DOCS_PAGES.find((page) => page.slug === slug);
}