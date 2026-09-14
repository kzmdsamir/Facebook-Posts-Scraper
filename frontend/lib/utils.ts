import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names with conflict resolution. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const numberFmt = new Intl.NumberFormat("en-US");

/** Full number formatting: 1,284 */
export function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return numberFmt.format(value);
}

const compactFmt = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** Compact formatting for KPI cards: 1.2K */
export function formatCompact(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return compactFmt.format(value);
}

const dateFmt = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
});

const dateTimeFmt = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
});

/**
 * Parse an ISO string or epoch value.
 * `timestamp` from the backend is an integer (epoch seconds); values above 1e12 are treated as epoch milliseconds.
 */
export function parseDate(input: string | number | null | undefined): Date | null {
  if (input == null || input === "") return null;
  let date: Date;
  if (typeof input === "number") {
    date = new Date(input > 1e12 ? input : input * 1000);
  } else {
    date = new Date(input);
  }
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(input: string | number | null | undefined): string {
  const date = parseDate(input);
  return date ? dateFmt.format(date) : "–";
}

export function formatDateTime(input: string | number | null | undefined): string {
  const date = parseDate(input);
  return date ? dateTimeFmt.format(date) : "–";
}

export function pluralize(count: number, singular: string): string {
  const label = count === 1 ? singular : `${singular}s`;
  return `${formatNumber(count)} ${label}`;
}

/** Collapse whitespace and truncate for table previews. */
export function truncateText(value: string | null | undefined, max = 160): string {
  if (!value) return "";
  const collapsed = value.replace(/\s+/g, " ").trim();
  if (collapsed.length <= max) return collapsed;
  return `${collapsed.slice(0, max).trimEnd()}…`;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/** Numeric sort key for a post (epoch ms): prefers `timestamp`, falls back to `published_at`. */
export function postSortDate(post: {
  timestamp: number | null;
  published_at: string | null;
}): number {
  if (post.timestamp != null && Number.isFinite(post.timestamp)) {
    return post.timestamp > 1e12 ? post.timestamp : post.timestamp * 1000;
  }
  const parsed = parseDate(post.published_at);
  return parsed ? parsed.getTime() : 0;
}