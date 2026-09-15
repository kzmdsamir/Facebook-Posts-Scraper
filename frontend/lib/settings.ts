/**
 * Persisted user settings (localStorage). Currently: default scrape options
 * that prefill the "New scrape" form.
 */
import type { PostType } from "./types";

const DEFAULTS_KEY = "postharvest-defaults";

export interface ScrapeDefaults {
  maxPosts: string;
  postType: "" | PostType;
  scrolls: string;
  useBrowser: boolean;
}

export const EMPTY_DEFAULTS: ScrapeDefaults = {
  maxPosts: "",
  postType: "",
  scrolls: "",
  useBrowser: false,
};

export function readScrapeDefaults(): ScrapeDefaults {
  const loaded = EMPTY_DEFAULTS;
  try {
    const raw = window.localStorage.getItem(DEFAULTS_KEY);
    if (!raw) return loaded;
    const parsed = JSON.parse(raw) as Partial<ScrapeDefaults>;
    if (typeof parsed.maxPosts === "string") loaded.maxPosts = parsed.maxPosts;
    if (parsed.postType === "text" || parsed.postType === "image" || parsed.postType === "video" || parsed.postType === "link") {
      loaded.postType = parsed.postType;
    }
    if (typeof parsed.scrolls === "string") loaded.scrolls = parsed.scrolls;
    if (typeof parsed.useBrowser === "boolean") loaded.useBrowser = parsed.useBrowser;
  } catch {
    // Unreadable JSON — fall back to the empty defaults.
  }
  return loaded;
}

export function writeScrapeDefaults(defaults: ScrapeDefaults): void {
  try {
    window.localStorage.setItem(DEFAULTS_KEY, JSON.stringify(defaults));
  } catch {
    // localStorage unavailable (private mode) — allow it to no-op.
  }
}