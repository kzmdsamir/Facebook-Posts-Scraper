"use client";

import { useMemo } from "react";
import { AlertTriangle, FileX2, MapPin, RefreshCcw } from "lucide-react";
import { ApiErrorBanner } from "@/components/api-error-banner";
import { Button } from "@/components/ui/button";
import { safeHttpUrl, type ApiError } from "@/lib/api";
import type { JobErrorDetail, JobProgress } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

export interface ProgressSectionProps {
  active: boolean;
  job: JobProgress | null;
  error: ApiError | null;
  onRetry: () => void;
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function computePercent(job: JobProgress): number | null {
  const pagesTotal = job.pages_total ?? 0;
  const pagesDone = job.pages_completed ?? 0;
  const postsFound = job.posts_found ?? 0;
  const postsProcessed = job.posts_processed ?? 0;

  if (job.status === "completed") return 100;

  // Multi-source: page stepping is the authoritative signal; we have no
  // per-source live counters, so stay coarse rather than blend aggregates.
  if (pagesTotal > 1) {
    return clampPercent(Math.round((pagesDone / pagesTotal) * 100));
  }

  if (job.status === "failed") {
    if (postsFound > 0 && postsProcessed > 0) {
      return clampPercent(Math.round((postsProcessed / postsFound) * 100));
    }
    return 0;
  }

  // Single source: live post counters give a smooth, truthful signal once the
  // scraper starts streaming them (the fetcher processing loop or the browser
  // post-parse phase). posts_extracted is an absolute cumulative counter, so
  // processed/found is a genuine fraction of the work done.
  if (pagesTotal === 1) {
    if (pagesDone >= 1) return 100;
    if (postsFound > 0 && postsProcessed > 0) {
      return clampPercent(Math.round((postsProcessed / postsFound) * 100));
    }
    // Still discovering (fetch/first parse): no counter to base a % on, so
    // show the indeterminate bar instead of a fake 0%.
    return null;
  }

  if (postsFound > 0 && postsProcessed > 0) {
    return clampPercent(Math.round((postsProcessed / postsFound) * 100));
  }
  return null;
}

function ErrorListItem({ entry }: { entry: JobErrorDetail }) {
  const link = safeHttpUrl(entry.url ?? entry.post_url);
  return (
    <li className="border border-neutral-200 bg-neutral-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="border border-red-700/60 px-1.5 py-0.5 font-sans font-light text-[10px] uppercase tracking-[0.2em] text-red-700">
          {entry.code}
        </span>
        <span className="min-w-0 flex-1 break-words font-sans text-sm text-neutral-700">{entry.message}</span>
      </div>
      {link ? (
        <p className="mt-1 truncate font-sans font-light text-[11px] text-neutral-500">
          <MapPin className="mr-1 inline h-3 w-3" aria-hidden="true" />
          {entry.post_url ?? entry.url}
        </p>
      ) : null}
    </li>
  );
}

export function ProgressSection({ active, job, error, onRetry }: ProgressSectionProps) {
  const percent = useMemo(() => (job ? computePercent(job) : null), [job]);
  const showUnreachable = error !== null && job === null;
  const showConnectionLoss = error !== null && job !== null;
  const failed = job?.status === "failed";
  const queued = job?.status === "queued";

  const stats = useMemo(() => {
    if (!job) return [];
    const rows: Array<{ label: string; value: string; danger?: boolean }> = [];
    if (job.pages_total != null) {
      rows.push({ label: "Pages", value: `${formatNumber(job.pages_completed)} / ${formatNumber(job.pages_total)}` });
    }
    rows.push({ label: "Posts found", value: formatNumber(job.posts_found) ?? "—" });
    rows.push({ label: "Posts processed", value: formatNumber(job.posts_processed) ?? "—" });
    rows.push({ label: "Duplicates", value: formatNumber(job.duplicates) ?? "—" });
    rows.push({ label: "Errors", value: formatNumber(job.errors) ?? "—", danger: (job.errors ?? 0) > 0 });
    return rows;
  }, [job]);

  const title = failed ? "Scraping failed" : queued ? "Job queued" : "Scraping in progress";

  const bar = percent != null ? (
    <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Job progress" className="relative h-1 w-full overflow-hidden bg-neutral-100">
      <div className={cn("h-full bg-black transition-[width] duration-500 ease-out progress-stripes", failed && "bg-red-600")} style={{ width: `${percent}%` }} />
    </div>
  ) : (
    <div role="progressbar" aria-label="Job progress" className="relative h-1 w-full overflow-hidden bg-neutral-100">
      <div className="h-full w-1/3 animate-indeterminate bg-black" />
    </div>
  );

  return (
    <>
      {showUnreachable ? (
        <ApiErrorBanner variant="warning" title="API unreachable" message={`${error?.message ?? "Cannot reach the backend."} The job keeps running server-side; reconnecting will resume updates.`} onRetry={onRetry} retryLabel="Retry now" />
      ) : null}

      <section className="border border-neutral-200 bg-white text-neutral-700" aria-label="Scraping monitor">
        {bar}

        <div className="flex items-center justify-between gap-4 px-4 py-2 border-b border-neutral-100">
          <div className="flex items-center gap-2 min-w-0 overflow-hidden">
            {failed ? (
              <AlertTriangle className="h-3 w-3 shrink-0 text-red-600" aria-hidden="true" />
            ) : (
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-600 animate-pulse-dot" aria-hidden="true" />
            )}
            <span className="font-sans font-light text-[10px] uppercase tracking-[0.2em] text-neutral-500 whitespace-nowrap">{title}</span>
            {job?.job_id ? (
              <span className="font-sans font-light text-[10px] uppercase tracking-[0.2em] text-neutral-400 tabular-nums whitespace-nowrap">
                · job {job.job_id.slice(0, 8)}
              </span>
            ) : null}
            {showConnectionLoss ? (
              <span className="font-sans font-light text-[10px] uppercase tracking-[0.2em] text-amber-500 whitespace-nowrap">
                · connection lost, retrying…
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {active && !showConnectionLoss ? (
              <span className="flex items-center gap-1 font-sans font-light text-[9px] uppercase tracking-[0.15em] text-neutral-400">
                <span className="h-1 w-1 rounded-full bg-emerald-500 animate-pulse" aria-hidden="true" />
                live
              </span>
            ) : null}
            {percent != null ? (
              <span className={cn("font-sans text-base font-semibold tracking-tighter tabular-nums leading-none", failed ? "text-red-600" : "text-black")}>
                {percent}%
              </span>
            ) : queued ? (
              <span className="font-sans font-light text-[10px] uppercase tracking-[0.2em] text-neutral-400">queued</span>
            ) : (
              <span className="font-sans font-light text-[10px] uppercase tracking-[0.2em] text-neutral-400">starting…</span>
            )}
          </div>
        </div>

        {stats.length > 0 ? (
          <div className="flex flex-wrap items-stretch divide-x divide-neutral-100">
            {stats.map((stat) => (
              <div key={stat.label} className="flex flex-col items-center justify-center px-4 py-2.5 flex-1 min-w-[72px]">
                <span className={cn("font-sans text-sm font-semibold tabular-nums leading-none", stat.danger ? "text-red-600" : "text-neutral-900")}>
                  {stat.value}
                </span>
                <span className="font-sans font-light text-[9px] uppercase tracking-[0.12em] text-neutral-400 mt-1 whitespace-nowrap">
                  {stat.label}
                </span>
              </div>
            ))}
            <div className="flex flex-col items-center justify-center px-4 py-2.5 min-w-[80px]">
              <span className="font-sans font-light text-[9px] uppercase tracking-[0.12em] text-neutral-400 whitespace-nowrap">
                {active ? "inputs locked" : "waiting"}
              </span>
            </div>
          </div>
        ) : null}

        {failed && job?.error_details && job.error_details.length > 0 ? (
          <div className="space-y-2 border-t border-neutral-200 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <h4 className="font-sans text-xs font-semibold text-neutral-900">
                <FileX2 className="mr-1.5 inline h-3.5 w-3.5 text-red-600" aria-hidden="true" />
                Error details ({job.error_details.length})
              </h4>
              <Button variant="outline" size="sm" onClick={onRetry} className="rounded-none border-neutral-200 bg-transparent text-neutral-600 hover:bg-neutral-100 hover:text-black">
                <RefreshCcw className="mr-1.5 h-3 w-3" aria-hidden="true" /> Refresh
              </Button>
            </div>
            <ul className="max-h-40 space-y-2 overflow-y-auto">
              {job.error_details.map((entry, index) => (
                <ErrorListItem key={`${entry.code}-${index}`} entry={entry} />
              ))}
            </ul>
          </div>
        ) : null}
      </section>
    </>
  );
}
