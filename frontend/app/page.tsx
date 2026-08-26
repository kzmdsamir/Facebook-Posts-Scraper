"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiErrorBanner } from "@/components/api-error-banner";
import { ExportArea } from "@/components/export-area";
import { Header } from "@/components/header";
import { KpiCards } from "@/components/kpi-cards";
import { PostDetailDrawer } from "@/components/post-detail-drawer";
import { PostsTable } from "@/components/posts-table";
import { ProgressSection } from "@/components/progress-section";
import { UrlInputCard } from "@/components/url-input-card";
import { ApiError, api, isTerminalStatus } from "@/lib/api";
import { useJobPosts, useJobProgress } from "@/lib/hooks";
import type { Post, ScrapeRequest } from "@/lib/types";

const POLL_INTERVAL_MS = 1500;

export default function HomePage() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [startError, setStartError] = useState<ApiError | null>(null);
  const [selectedPost, setSelectedPost] = useState<Post | null>(null);
  const lastRequestRef = useRef<ScrapeRequest | null>(null);
  const resultsRef = useRef<HTMLDivElement | null>(null);

  const { job, error: pollError, retry: retryPoll } = useJobProgress(jobId, { pollMs: POLL_INTERVAL_MS });
  const postsState = useJobPosts(job && isTerminalStatus(job.status) ? jobId : null);

  const jobActive = jobId !== null && job !== null && !isTerminalStatus(job.status) ? true : jobId !== null && job === null;
  const jobTerminal = job !== null && isTerminalStatus(job.status);

  // Scroll to results once the job finishes.
  useEffect(() => {
    if (jobTerminal) {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [jobTerminal]);

  const handleStart = useCallback(async (request: ScrapeRequest) => {
    lastRequestRef.current = request;
    setSubmitting(true);
    setStartError(null);
    try {
      const response = await api.startScrape(request);
      setJobId(response.job_id);
      setSelectedPost(null);
    } catch (error) {
      setStartError(
        error instanceof ApiError ? error : new ApiError({ code: "network_error", message: "Failed to start the job." })
      );
    } finally {
      setSubmitting(false);
    }
  }, []);

  const handleReset = useCallback(() => {
    setJobId(null);
    setSelectedPost(null);
    setStartError(null);
  }, []);

  const retryStart = useCallback(() => {
    if (lastRequestRef.current) {
      void handleStart(lastRequestRef.current);
    }
  }, [handleStart]);

  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 pb-16 pt-6 sm:px-6 lg:pt-8">
        <UrlInputCard disabled={jobActive} submitting={submitting} onSubmit={handleStart} />

        {startError ? (
          <ApiErrorBanner
            title="Could not start the job"
            message={startError.message}
            onRetry={retryStart}
            retryLabel="Try again"
          />
        ) : null}

        {jobId && !jobTerminal ? (
          <ProgressSection active={jobActive} job={job} error={pollError} onRetry={retryPoll} />
        ) : null}

        {jobTerminal ? (
          <div ref={resultsRef} className="scroll-mt-24 space-y-6" aria-live="polite">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-xl font-semibold tracking-tight">
                {job?.status === "failed" ? "Results (partial)" : "Results"}
              </h2>
              <p className="max-w-lg truncate text-xs text-muted-foreground">
                Job <code className="rounded bg-muted px-1.5 py-0.5 font-mono">{jobId}</code>
                {job?.pages_total != null ? ` · ${job.pages_total} page${job.pages_total === 1 ? "" : "s"}` : ""}
              </p>
            </div>

            <KpiCards
              posts={postsState.posts}
              total={postsState.total}
              capped={postsState.capped}
              loading={postsState.loading}
              error={postsState.error?.message ?? null}
              onRetry={postsState.reload}
            />

            <PostsTable
              posts={postsState.posts}
              total={postsState.total}
              loading={postsState.loading}
              loaded={postsState.loaded}
              error={postsState.error?.message ?? null}
              onRetry={postsState.reload}
              onSelectPost={setSelectedPost}
            />

            <ExportArea jobId={jobId} status={job?.status ?? null} onNewScrape={handleReset} />
          </div>
        ) : null}
      </main>

      <footer className="border-t bg-muted/30">
        <div className="mx-auto w-full max-w-7xl px-4 py-4 text-center text-xs text-muted-foreground sm:px-6">
          Facebook Posts Scraper — for authorized use only. Processes publicly available content with rate limiting and
          no authentication bypass. Facebook content is untrusted input and is always rendered as plain text.
        </div>
      </footer>

      <PostDetailDrawer post={selectedPost} open={selectedPost !== null} onClose={() => setSelectedPost(null)} />
    </div>
  );
}