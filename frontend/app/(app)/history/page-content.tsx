"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, RefreshCw } from "lucide-react";
import { Eyebrow, PageHeading } from "@/components/display";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { JobSummary } from "@/lib/types";
import { formatCompact, formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 25;

function StatusBadge({ status }: { status: JobSummary["status"] }) {
  const runningOrQueued = status === "running" || status === "queued";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.2em]",
        status === "failed"
          ? "border-foreground bg-foreground text-background"
          : runningOrQueued
            ? "border-highlight text-highlight"
            : "border-border text-muted-foreground",
      )}
    >
      {runningOrQueued ? <span className="h-1 w-1 rounded-full bg-highlight animate-pulse-dot" aria-hidden="true" /> : null}
      {status}
    </span>
  );
}

export default function HistoryPage() {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listJobs({ page, page_size: PAGE_SIZE });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load job history");
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((job) => {
      const haystack = [job.job_id, ...job.urls].join(" ").toLowerCase();
      return haystack.includes(q);
    });
  }, [items, query]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="animate-fade-in-up space-y-8">
      <header className="border-b border-border pb-8">
        <Eyebrow>{`${total} run${total === 1 ? "" : "s"} stored`}</Eyebrow>
        <PageHeading>History</PageHeading>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
          Every scrape ever started, in order. Reopen a finished run for its full results and exports, or
          watch a live one land.
        </p>
      </header>

      <section className="border border-foreground" aria-label="Runs history">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="relative w-full sm:max-w-xs">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search id or URL…"
              aria-label="Search runs"
              className="h-8 rounded-none border-foreground bg-background px-3 font-mono text-xs focus-visible:ring-2 focus-visible:ring-highlight"
            />
          </div>
          {error ? (
            <button
              type="button"
              onClick={() => void load()}
              className="flex items-center gap-1.5 border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground transition-colors hover:text-foreground"
            >
              <RefreshCw className="h-3 w-3" strokeWidth={1.75} /> retry
            </button>
          ) : (
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground tabular-nums">
              page {page} / {pages}
            </span>
          )}
        </div>

        {error ? (
          <p className="px-4 py-6 font-mono text-xs text-highlight">{error}</p>
        ) : loading && items.length === 0 ? (
          <p className="px-4 py-10 text-center font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
            loading runs…
          </p>
        ) : filtered.length === 0 ? (
          <div className="px-4 py-14 text-center">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
              {query ? "No runs match your search" : "No runs yet"}
            </p>
            {!query ? (
              <Link href="/" className="mt-3 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
                Start a new scrape <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.75} />
              </Link>
            ) : null}
          </div>
        ) : (
          <>
            <div className="hidden grid-cols-12 gap-2 border-b-2 border-foreground bg-background px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground sm:grid">
              <span className="col-span-2">id</span>
              <span className="col-span-2">when</span>
              <span className="col-span-3">sources</span>
              <span className="col-span-1">posts</span>
              <span className="col-span-1">pages</span>
              <span className="col-span-2">status</span>
              <span className="col-span-1 text-right">open</span>
            </div>

            <ul className="divide-y divide-border">
              {filtered.map((job) => (
                <li
                  key={job.job_id}
                  className="group grid grid-cols-12 items-center gap-2 px-4 py-3 transition-colors hover:bg-neutral-50"
                >
                  <span className="col-span-2 truncate font-mono text-xs text-muted-foreground">{job.job_id.slice(0, 8)}</span>
                  <span className="col-span-2 truncate font-mono text-xs text-muted-foreground" title={job.created_at ?? undefined}>
                    {formatDateTime(job.created_at)}
                  </span>
                  <span className="col-span-3 truncate font-mono text-xs text-muted-foreground" title={job.urls.join("\n")}>
                    {job.urls.length > 0 ? job.urls[0] : "—"}
                    {job.urls.length > 1 ? ` +${job.urls.length - 1}` : ""}
                  </span>
                  <span className="col-span-1 font-mono text-xs tabular-nums text-foreground">
                    {formatCompact(job.posts_processed)}
                    {job.posts_found !== job.posts_processed ? (
                      <span className="text-muted-foreground">/{formatCompact(job.posts_found)}</span>
                    ) : null}
                  </span>
                  <span className="col-span-1 font-mono text-xs tabular-nums text-muted-foreground">
                    {formatCompact(job.pages_completed)}/{formatCompact(job.pages_total)}
                  </span>
                  <span className="col-span-2">
                    <StatusBadge status={job.status} />
                  </span>
                  <span className="col-span-1 text-right">
                    <Link
                      href={`/investigation?job=${job.job_id}`}
                      aria-label={`Open run ${job.job_id}`}
                      className="inline-flex items-center gap-1 border border-transparent px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground transition-colors hover:border-foreground hover:text-foreground sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100"
                    >
                      open <ArrowRight className="h-3 w-3" strokeWidth={1.75} />
                    </Link>
                  </span>
                </li>
              ))}
            </ul>

            <div className="flex items-center justify-between border-t border-border px-4 py-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground tabular-nums">
                {total} total
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-none"
                >
                  <ArrowLeft className="h-3 w-3" strokeWidth={1.75} /> Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= pages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-none"
                >
                  Next <ArrowRight className="h-3 w-3" strokeWidth={1.75} />
                </Button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}