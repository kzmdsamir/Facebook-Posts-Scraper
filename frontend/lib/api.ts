/**
 * Typed API client for the Facebook Posts Scraper backend.
 *
 * All post text and URLs rendered in the UI must never be trusted: use
 * `safeHttpUrl()` before putting a URL into an href, and let React escape
 * text (we never use dangerouslySetInnerHTML anywhere in this app).
 */
import type {
  ApiErrorBody,
  ExportFormat,
  JobProgress,
  JobStatus,
  PaginatedPosts,
  Post,
  ScrapeRequest,
  ScrapeResponse,
} from "./types";

/** Resolved at build time. Defaults to the local backend. */
export const API_BASE: string = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const TERMINAL_STATUSES: ReadonlySet<string> = new Set(["completed", "failed"]);

export function isTerminalStatus(status: JobStatus | string | undefined | null): boolean {
  return status != null && TERMINAL_STATUSES.has(status);
}

/** Error with an API error code; thrown for both HTTP error responses and network failures. */
export class ApiError extends Error {
  readonly status?: number;
  readonly code: string;
  readonly details?: unknown;

  constructor(options: { status?: number; code: string; message: string; details?: unknown }) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError({
      code: "network_error",
      message: `API unreachable at ${API_BASE}. Is the backend running and is CORS enabled for this origin?`,
    });
  }

  if (!response.ok) {
    let code = "http_error";
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = (await response.json()) as Partial<ApiErrorBody> | null;
      if (body?.error) {
        code = typeof body.error.code === "string" ? body.error.code : code;
        message = typeof body.error.message === "string" ? body.error.message : message;
      }
    } catch {
      // Non-JSON error body — keep the generic message.
    }
    throw new ApiError({ status: response.status, code, message });
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Normalize a raw job payload (backend may omit nullable fields). */
function normalizeJob(raw: Partial<JobProgress>): JobProgress {
  const status = raw?.status ?? "queued";
  return {
    job_id: raw?.job_id ?? null,
    status: TERMINAL_STATUSES.has(status) || status === "running" || status === "queued" ? status : "queued",
    pages_total: raw?.pages_total ?? null,
    pages_completed: raw?.pages_completed ?? null,
    posts_found: raw?.posts_found ?? null,
    posts_processed: raw?.posts_processed ?? null,
    duplicates: raw?.duplicates ?? null,
    errors: raw?.errors ?? null,
    error_details: raw?.error_details ?? [],
  };
}

function normalizePost(raw: Partial<Post>): Post {
  return {
    post_id: raw?.post_id ?? null,
    facebook_url: raw?.facebook_url ?? null,
    post_url: raw?.post_url ?? null,
    page_name: raw?.page_name ?? null,
    page_id: raw?.page_id ?? null,
    profile_url: raw?.profile_url ?? null,
    post_type: raw?.post_type ?? null,
    published_at: raw?.published_at ?? null,
    timestamp: raw?.timestamp ?? null,
    text: raw?.text ?? null,
    caption: raw?.caption ?? null,
    hashtags: Array.isArray(raw?.hashtags) ? raw.hashtags : [],
    mentions: Array.isArray(raw?.mentions) ? raw.mentions : [],
    external_links: Array.isArray(raw?.external_links) ? raw.external_links : [],
    likes: raw?.likes ?? null,
    reactions: raw?.reactions ?? null,
    comments_count: raw?.comments_count ?? null,
    shares: raw?.shares ?? null,
    views_count: raw?.views_count ?? null,
    reaction_like_count: raw?.reaction_like_count ?? null,
    reaction_love_count: raw?.reaction_love_count ?? null,
    reaction_care_count: raw?.reaction_care_count ?? null,
    reaction_haha_count: raw?.reaction_haha_count ?? null,
    reaction_wow_count: raw?.reaction_wow_count ?? null,
    reaction_sad_count: raw?.reaction_sad_count ?? null,
    reaction_angry_count: raw?.reaction_angry_count ?? null,
    media_type: raw?.media_type ?? null,
    thumbnail_url: raw?.thumbnail_url ?? null,
    media_url: raw?.media_url ?? null,
    video_url: raw?.video_url ?? null,
    transcript: raw?.transcript ?? null,
    transcript_language: raw?.transcript_language ?? null,
  };
}

export const api = {
  /** POST /api/scrape */
  async startScrape(requestBody: ScrapeRequest): Promise<ScrapeResponse> {
    return request<ScrapeResponse>("/api/scrape", {
      method: "POST",
      body: JSON.stringify(requestBody),
    });
  },

  /** GET /api/jobs/{job_id} */
  async getJob(jobId: string): Promise<JobProgress> {
    const raw = await request<Partial<JobProgress>>(`/api/jobs/${encodeURIComponent(jobId)}`);
    return normalizeJob(raw);
  },

  /** GET /api/jobs/{job_id}/posts (paginated) */
  async getPosts(jobId: string, params: { page?: number; page_size?: number } = {}): Promise<PaginatedPosts> {
    const query = new URLSearchParams();
    if (params.page != null) query.set("page", String(params.page));
    if (params.page_size != null) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const raw = await request<Partial<PaginatedPosts>>(`/api/jobs/${encodeURIComponent(jobId)}/posts${suffix}`);
    return {
      items: (Array.isArray(raw?.items) ? raw.items : []).map(normalizePost),
      total: raw?.total ?? 0,
      page: raw?.page ?? 1,
      page_size: raw?.page_size ?? params.page_size ?? 0,
    };
  },

  /** DELETE /api/jobs/{job_id} (kept for completeness; the dashboard does not auto-delete) */
  async deleteJob(jobId: string): Promise<void> {
    return request<void>(`/api/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
  },

  /** Absolute URL for the live export endpoints (JSON/CSV/XLSX). */
  getExportUrl(jobId: string, format: ExportFormat): string {
    return `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/export/${format}`;
  },
};

/**
 * Only http(s) URLs survive; everything else (javascript:, data:, control chars) is rejected.
 * Returns null when the input is unsafe.
 */
export function safeHttpUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!/^https?:\/\//i.test(trimmed)) return null;
  if (/[\u0000-\u001f\u007f]/.test(trimmed)) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    if (!parsed.hostname) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

export interface FacebookUrlCheck {
  valid: boolean;
  normalized: string | null;
  reason: string | null;
}

/**
 * Client-side Facebook URL validation (the backend re-validates authoritatively).
 * Accepts https://(<sub>.)facebook.com/<path> — page, profile and /profile.php?id= forms.
 */
export function isFacebookUrl(raw: string): FacebookUrlCheck {
  const trimmed = raw.trim();
  if (!trimmed) return { valid: false, normalized: null, reason: "Empty URL." };

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return { valid: false, normalized: null, reason: "Not a valid URL." };
  }

  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    return { valid: false, normalized: null, reason: "URL must start with http:// or https://." };
  }

  const host = parsed.hostname.toLowerCase();
  const isFacebookHost = host === "facebook.com" || host.endsWith(".facebook.com");
  if (!isFacebookHost) {
    return { valid: false, normalized: null, reason: `"${host}" is not a facebook.com address.` };
  }

  if (parsed.pathname.length <= 1) {
    return { valid: false, normalized: null, reason: "Provide a page or profile path, e.g. /yourpage." };
  }

  const normalized = parsed.toString().replace(/\/+$/, "");
  return { valid: true, normalized, reason: null };
}