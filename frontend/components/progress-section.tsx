"use client";

import { useMemo } from "react";
import { AlertTriangle, FileX2, Loader2, MapPin, RefreshCcw } from "lucide-react";
import { ApiErrorBanner } from "@/components/api-error-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { safeHttpUrl, type ApiError } from "@/lib/api";
import type { JobErrorDetail, JobProgress } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

export interface ProgressSectionProps {
  /** True while a job exists and has not reached a terminal state. */
  active: boolean;
  job: JobProgress | null;
  /** Polling/network error (API unreachable). */
  error: ApiError | null;
  onRetry: () => void;
}

interface StatRow {
  label: string;
  value: string | null;
  tone?: "default" | "danger";
}

function computePercent(job: JobProgress): number | null {
  // Pages-first: pages_completed / pages_total.
  if (job.pages_total != null && job.pages_total > 0 && job.pages_completed != null) {
    return Math.max(0, Math.min(100, Math.round((job.pages_completed / job.pages_total) * 100)));
  }
  // Fall back to posts_processed / posts_found.
  if (job.posts_found != null && job.posts_found > 0 && job.posts_processed != null) {
    return Math.max(0, Math.min(100, Math.round((job.posts_processed / job.posts_found) * 100)));
  }
  return null;
}

function ErrorListItem({ entry }: { entry: JobErrorDetail }) {
  const link = safeHttpUrl(entry.url ?? entry.post_url);
  return (
    <li className="rounded-lg border bg-card p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="destructive">{entry.code}</Badge>
        <span className="min-w-0 flex-1 break-words text-sm">{entry.message}</span>
      </div>
      {link ? (
        <p className="mt-1 truncate text-xs text-muted-foreground">
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

  const stats: StatRow[] = useMemo(() => {
    if (!job) return [];
    const rows: StatRow[] = [];
    if (job.pages_total != null) {
      rows.push({
        label: "Pages",
        value: `${formatNumber(job.pages_completed)} / ${formatNumber(job.pages_total)}`,
      });
    }
    rows.push({ label: "Posts found", value: formatNumber(job.posts_found) ?? null });
    rows.push({ label: "Posts processed", value: formatNumber(job.posts_processed) ?? null });
    rows.push({ label: "Duplicates", value: formatNumber(job.duplicates) ?? null });
    rows.push({
      label: "Errors",
      value: formatNumber(job.errors) ?? null,
      tone: (job.errors ?? 0) > 0 ? "danger" : "default",
    });
    return rows;
  }, [job]);

  return (
    <Card id="progress" className="scroll-mt-20">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2">
              {job?.status === "failed" ? (
                <AlertTriangle className="h-4 w-4 text-destructive" aria-hidden="true" />
              ) : (
                <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
              )}
              {job?.status === "failed" ? "Scraping failed" : job?.status === "queued" ? "Job queued" : "Scraping in progress"}
            </CardTitle>
            <CardDescription className="mt-1">
              {job?.status === "queued"
                ? "Waiting for the worker to pick up the job…"
                : job?.status === "failed"
                  ? "The job ended with errors. Partial results may still be available below."
                  : "Live status updates from the backend — you can keep this tab open."}
            </CardDescription>
          </div>
          {percent != null ? (
            <div className="shrink-0 text-right">
              <p className="text-2xl font-bold tabular-nums">{percent}%</p>
              {job ? <p className="text-xs text-muted-foreground">job {job.job_id ?? ""}</p> : null}
            </div>
          ) : (
            <Badge variant="secondary">starting…</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {showUnreachable ? (
          <ApiErrorBanner
            variant="warning"
            title="API unreachable"
            message={`${error?.message ?? "Cannot reach the backend."} The job keeps running server-side; reconnecting will resume updates.`}
            onRetry={onRetry}
            retryLabel="Retry now"
          />
        ) : null}

        {showConnectionLoss ? (
          <p className="flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-600 dark:text-amber-400" role="status">
            <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-amber-500" aria-hidden="true" />
            Connection to the API was interrupted — updates paused, retrying in the background.
          </p>
        ) : null}

        <Progress value={percent} max={100} className="h-3" />

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {stats.length > 0
            ? stats.map((stat) => (
                <div key={stat.label} className="rounded-lg border bg-muted/30 px-3 py-2.5">
                  <p className="text-xs text-muted-foreground">{stat.label}</p>
                  <p className={stat.tone === "danger" ? "text-lg font-semibold tabular-nums text-destructive" : "text-lg font-semibold tabular-nums"}>
                    {stat.value ?? "—"}
                  </p>
                </div>
              ))
            : Array.from({ length: 5 }).map((_, index) => (
                <div key={index} className="animate-pulse rounded-lg border bg-muted/30 px-3 py-2.5">
                  <div className="h-3 w-16 rounded bg-muted-foreground/20" />
                  <div className="mt-2 h-5 w-10 rounded bg-muted-foreground/20" />
                </div>
              ))}
        </div>

        {job?.status === "failed" ? (
          <div className="space-y-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
            <div className="flex items-center justify-between gap-3">
              <h4 className="flex items-center gap-2 text-sm font-semibold">
                <FileX2 className="h-4 w-4 text-destructive" aria-hidden="true" />
                {job.error_details && job.error_details.length > 0
                  ? `Error details (${job.error_details.length})`
                  : "The job reported a failure with no additional detail."}
              </h4>
              <Button variant="outline" size="sm" onClick={onRetry}>
                <RefreshCcw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" /> Refresh
              </Button>
            </div>
            {job.error_details && job.error_details.length > 0 ? (
              <ul className="max-h-52 space-y-2 overflow-y-auto pr-1">
                {job.error_details.map((entry, index) => (
                  <ErrorListItem key={`${entry.code}-${index}`} entry={entry} />
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}