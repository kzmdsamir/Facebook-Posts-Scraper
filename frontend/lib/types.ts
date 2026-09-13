/**
 * Shared frontend types — mirrors the backend API DTOs (see plan.md canonical contracts).
 * Every field on Post is nullable (or an array) because extrated data may be incomplete;
 * missing values are never fabricated by the backend.
 */

export type PostType = "text" | "image" | "video" | "link";

export type JobStatus = "queued" | "running" | "completed" | "failed";

export type ExportFormat = "json" | "csv" | "excel";

/** POST /api/scrape request body */
export interface ScrapeRequest {
  urls: string[];
  max_posts?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  post_type?: PostType | null;
  use_browser?: boolean;
  account?: string | null;
  scrolls?: number | null;
}

/** POST /api/scrape response */
export interface ScrapeResponse {
  job_id: string;
  status: JobStatus;
}

/** One entry in GET /api/jobs/{id} -> error_details */
export interface JobErrorDetail {
  url?: string | null;
  post_url?: string | null;
  code: string;
  message: string;
}

/** GET /api/jobs/{id} response (fields may be null until the job reports them) */
export interface JobProgress {
  job_id?: string | null;
  status: JobStatus;
  pages_total: number | null;
  pages_completed: number | null;
  posts_found: number | null;
  posts_processed: number | null;
  duplicates: number | null;
  errors: number | null;
  error_details?: JobErrorDetail[] | null;
}

/** Normalized Facebook post (single source of truth from plan.md) */
export interface Post {
  post_id: string | null;
  facebook_url: string | null;
  post_url: string | null;
  page_name: string | null;
  page_id: string | null;
  profile_url: string | null;
  post_type: PostType | null;
  published_at: string | null;
  timestamp: number | null;

  text: string | null;
  caption: string | null;
  hashtags: string[];
  mentions: string[];
  external_links: string[];

  likes: number | null;
  reactions: number | null;
  comments_count: number | null;
  shares: number | null;
  views_count: number | null;

  reaction_like_count: number | null;
  reaction_love_count: number | null;
  reaction_care_count: number | null;
  reaction_haha_count: number | null;
  reaction_wow_count: number | null;
  reaction_sad_count: number | null;
  reaction_angry_count: number | null;

  media_type: string | null;
  thumbnail_url: string | null;
  media_url: string | null;
  video_url: string | null;
  transcript: string | null;
  transcript_language: string | null;
}

/** GET /api/jobs/{id}/posts response (paginated) */
export interface PaginatedPosts {
  items: Post[];
  total: number;
  page: number;
  page_size: number;
}

/** One row in GET /api/jobs (history) */
export interface JobSummary {
  job_id: string;
  status: JobStatus;
  pages_total: number;
  pages_completed: number;
  posts_found: number;
  posts_processed: number;
  duplicates: number;
  errors: number;
  urls: string[];
  max_posts?: number | null;
  post_type?: string | null;
  created_at?: string | null;
  completed_at?: string | null;
}

/** GET /api/jobs response (paginated history) */
export interface JobListResponse {
  items: JobSummary[];
  total: number;
  page: number;
  page_size: number;
}

/** Metadata row in GET /api/accounts */
export interface AccountSession {
  name: string;
  cookies_file?: string | null;
  saved_at?: string | null;
}

/** GET /api/accounts response */
export interface AccountsResponse {
  items: AccountSession[];
  total: number;
}

/** Standard error body: {"error": {"code": "...", "message": "..."}} */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}

export const POST_TYPE_LABELS: Record<string, string> = {
  text: "Text",
  image: "Image",
  video: "Video",
  link: "Link",
};

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export const EXPORT_FILENAMES: Record<ExportFormat, string> = {
  json: "facebook_posts.json",
  csv: "facebook_posts.csv",
  excel: "facebook_posts.xlsx",
};