"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ApiErrorBanner } from "@/components/api-error-banner";
import { ExportArea } from "@/components/export-area";
import { KpiCards } from "@/components/kpi-cards";
import { PostDetailDrawer } from "@/components/post-detail-drawer";
import { PostsTable } from "@/components/posts-table";
import { ProgressSection } from "@/components/progress-section";
import { UrlInputCard } from "@/components/url-input-card";
import { ApiError, api, isTerminalStatus } from "@/lib/api";
import { useJobPosts, useJobProgress } from "@/lib/hooks";
import type { Post, ScrapeRequest } from "@/lib/types";

const POLL_INTERVAL_MS = 1500;

const DOT_STEP_MS = 400;
const DOT_MAX = 4;

function ScraperRunningHeading() {
  const [dots, setDots] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setDots((d) => (d >= DOT_MAX ? 0 : d + 1));
    }, DOT_STEP_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="font-mono tabular-nums">
      Scraper Running
      {".".repeat(dots)}
      <span className="invisible aria-hidden" aria-hidden="true">{`${"=".repeat(DOT_MAX)}`}</span>
    </span>
  );
}

export default function InvestigationPage() {
  return (
    <Suspense fallback={null}>
      <InvestigationContent />
    </Suspense>
  );
}

function InvestigationContent() {
  const searchParams = useSearchParams();
  const urlParam = searchParams.get("url");
  const urlJobParam = searchParams.get("job");

  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [startError, setStartError] = useState<ApiError | null>(null);
  const [selectedPost, setSelectedPost] = useState<Post | null>(null);
  const [formDismissed, setFormDismissed] = useState(false);
  const lastRequestRef = useRef<ScrapeRequest | null>(null);
  const resultsRef = useRef<HTMLDivElement | null>(null);

  // History deep links /?job=... → /investigation?job=... reopen a past run.
  useEffect(() => {
    setJobId(urlJobParam);
    if (urlJobParam) setFormDismissed(true);
  }, [urlJobParam]);

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
      setFormDismissed(true);
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
    <>
      <div className="mx-auto w-full max-w-5xl px-8 pb-20 animate-fade-in-up">
        <AnimatePresence mode="wait" initial={false}>
          {jobActive ? (
            <motion.h1
              key="running"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="mb-8 pt-6 font-sans text-4xl font-semibold tracking-tighter text-black"
            >
              <ScraperRunningHeading />
            </motion.h1>
          ) : jobTerminal ? (
            <motion.h1
              key="results"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="mb-8 pt-6 font-sans text-4xl font-semibold tracking-tighter text-black"
            >
              {job?.status === "failed" ? "Results (partial)" : "Results"}
            </motion.h1>
          ) : (
            <motion.h1
              key="idle"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="mb-8 pt-6 font-sans text-4xl font-semibold tracking-tighter text-black"
            >
              Target, configure, run.
            </motion.h1>
          )}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {!formDismissed ? (
            <motion.div
              key="url-input-card"
              exit={{ opacity: 0, height: 0, marginBottom: 0 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="overflow-hidden"
            >
              <UrlInputCard
                initialUrls={urlParam ?? undefined}
                disabled={jobActive}
                submitting={submitting}
                onSubmit={handleStart}
                onClearError={() => setStartError(null)}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>

        {startError ? (
          <div className="mt-6">
            <ApiErrorBanner
              title="Could not start the job"
              message={startError.message}
              onRetry={retryStart}
              retryLabel="Try again"
            />
          </div>
        ) : null}

        {jobId && !jobTerminal ? (
          <div className="mt-10 border-t border-neutral-200 pt-8">
            <ProgressSection active={jobActive} job={job} error={pollError} onRetry={retryPoll} />
          </div>
        ) : null}

        {jobTerminal ? (
          <div ref={resultsRef} className="mt-10 scroll-mt-24 space-y-6 border-t border-neutral-200 pt-8" aria-live="polite">
            <p className="max-w-lg truncate font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Job <code className="border border-border px-1.5 py-0.5">{jobId}</code>
              {job?.pages_total != null ? ` · ${job.pages_total} page${job.pages_total === 1 ? "" : "s"}` : ""}
            </p>

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
      </div>

      <PostDetailDrawer post={selectedPost} open={selectedPost !== null} onClose={() => setSelectedPost(null)} />
    </>
  );
}