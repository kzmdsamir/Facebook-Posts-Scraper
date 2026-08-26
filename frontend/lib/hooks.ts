"use client";

/**
 * Client-side data hooks used by the dashboard. Keeping them here means the
 * page component stays declarative and the polling/fetch logic is testable.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, isTerminalStatus } from "./api";
import type { JobProgress, Post } from "./types";

export interface JobProgressState {
  job: JobProgress | null;
  error: ApiError | null;
  retry: () => void;
}

/**
 * Polls GET /api/jobs/{id} every `pollMs` until the job reaches a terminal
 * state (completed/failed). On network failure the poll backs off but keeps
 * trying; `retry()` forces an immediate poll.
 */
export function useJobProgress(jobId: string | null, options: { pollMs?: number } = {}): JobProgressState {
  const pollMs = options.pollMs ?? 1500;
  const [job, setJob] = useState<JobProgress | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const lastJobIdRef = useRef<string | null>(null);

  useEffect(() => {
    // Reset immediately when the target job changes (avoids flashing stale progress).
    if (jobId !== lastJobIdRef.current) {
      lastJobIdRef.current = jobId;
      setJob(null);
      setError(null);
    }
    if (!jobId) {
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const tick = async (): Promise<void> => {
      try {
        const next = await api.getJob(jobId);
        if (cancelled) return;
        setJob(next);
        setError(null);
        if (isTerminalStatus(next.status)) return; // done polling
        timer = setTimeout(() => {
          void tick();
        }, pollMs);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err : new ApiError({ code: "network_error", message: "Failed to reach the API." }));
        timer = setTimeout(() => {
          void tick();
        }, Math.min(pollMs * 2, 8000));
      }
    };

    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, pollMs, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  return { job, error, retry };
}

export interface JobPostsState {
  posts: Post[];
  total: number;
  capped: boolean;
  loading: boolean;
  error: ApiError | null;
  loaded: boolean;
  reload: () => void;
}

/**
 * Loads all posts for a finished job by walking the paginated endpoint.
 * A hard cap prevents unbounded memory use (spec §15); the UI shows a note
 * when the dataset is larger than the cap.
 */
export function useJobPosts(
  jobId: string | null,
  options: { pageSize?: number; maxPosts?: number } = {}
): JobPostsState {
  const { pageSize = 200, maxPosts = 2000 } = options;
  const [state, setState] = useState<Omit<JobPostsState, "reload">>({
    posts: [],
    total: 0,
    capped: false,
    loading: false,
    error: null,
    loaded: false,
  });
  const [attempt, setAttempt] = useState(0);
  const lastJobIdRef = useRef<string | null>(null);

  useEffect(() => {
    // Reset results when switching to a different job.
    if (jobId !== lastJobIdRef.current) {
      lastJobIdRef.current = jobId;
      setState({ posts: [], total: 0, capped: false, loading: false, error: null, loaded: false });
    }
    if (!jobId) {
      return;
    }

    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));

    (async () => {
      try {
        const all: Post[] = [];
        let page = 1;
        let total = 0;
        let capped = false;

        for (;;) {
          const result = await api.getPosts(jobId, { page, page_size: pageSize });
          total = result.total;
          all.push(...result.items);
          if (all.length >= maxPosts) {
            capped = true;
            break;
          }
          if (result.items.length === 0 || all.length >= total) break;
          page += 1;
        }

        if (cancelled) return;
        setState({ posts: all, total, capped, loading: false, error: null, loaded: true });
      } catch (err) {
        if (cancelled) return;
        setState((previous) => ({
          ...previous,
          loading: false,
          error: err instanceof ApiError ? err : new ApiError({ code: "network_error", message: "Failed to load posts." }),
        }));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [jobId, pageSize, maxPosts, attempt]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  return { ...state, reload };
}