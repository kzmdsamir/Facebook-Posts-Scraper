"use client";

import { useMemo } from "react";
import {
  FileText,
  Image as ImageIcon,
  Link2,
  MessageCircle,
  Share2,
  ThumbsUp,
  Video,
} from "lucide-react";
import { ApiErrorBanner } from "@/components/api-error-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Post } from "@/lib/types";
import { formatCompact, formatNumber, pluralize } from "@/lib/utils";

export interface KpiCardsProps {
  posts: Post[];
  /** Server-reported total post count (may exceed loaded posts when capped). */
  total: number;
  /** True when the dataset exceeds the load cap, so aggregates are partial. */
  capped: boolean;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

interface Kpi {
  label: string;
  value: string;
  caption: string;
  icon: typeof ThumbsUp;
  tone: string;
}

const ICON_TONES: Record<string, string> = {
  blue: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  emerald: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  violet: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  amber: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  rose: "bg-rose-500/15 text-rose-600 dark:text-rose-400",
  slate: "bg-slate-500/15 text-slate-600 dark:text-slate-300",
};

export function KpiCards({ posts, total, capped, loading, error, onRetry }: KpiCardsProps) {
  const aggregates = useMemo(() => {
    let likes = 0;
    let comments = 0;
    let shares = 0;
    let videos = 0;
    let images = 0;
    let links = 0;
    for (const post of posts) {
      likes += post.likes ?? 0;
      comments += post.comments_count ?? 0;
      shares += post.shares ?? 0;
      const mediaType = (post.media_type ?? "").toLowerCase();
      if (mediaType === "video" || post.post_type === "video") videos += 1;
      if (mediaType === "image" || post.post_type === "image") images += 1;
      if (post.post_type === "link" || (post.external_links?.length ?? 0) > 0) links += 1;
    }
    return { likes, comments, shares, videos, images, links };
  }, [posts]);

  const kpis: Kpi[] = useMemo(() => {
    const loadedCaption = capped
      ? `first ${formatNumber(posts.length)} loaded of ${formatNumber(total)}`
      : posts.length === 1
        ? "1 post loaded"
        : `${formatNumber(posts.length)} posts loaded`;
    return [
      { label: "Total Posts", value: formatNumber(total || posts.length), caption: capped ? `dataset: ${formatNumber(total)}` : loadedCaption, icon: FileText, tone: "blue" },
      { label: "Total Likes", value: formatCompact(aggregates.likes), caption: pluralize(aggregates.likes, "like"), icon: ThumbsUp, tone: "emerald" },
      { label: "Total Comments", value: formatCompact(aggregates.comments), caption: pluralize(aggregates.comments, "comment"), icon: MessageCircle, tone: "violet" },
      { label: "Total Shares", value: formatCompact(aggregates.shares), caption: pluralize(aggregates.shares, "share"), icon: Share2, tone: "amber" },
      { label: "Videos", value: formatNumber(aggregates.videos), caption: "video / reel posts", icon: Video, tone: "rose" },
      { label: "Images", value: formatNumber(aggregates.images), caption: "photo posts", icon: ImageIcon, tone: "slate" },
      { label: "Links", value: formatNumber(aggregates.links), caption: "link posts", icon: Link2, tone: "blue" },
    ];
  }, [aggregates, capped, posts.length, total]);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle>Results overview</CardTitle>
        {capped ? (
          <p className="rounded-full bg-warning/15 px-3 py-1 text-xs font-medium text-amber-600 dark:text-amber-400">
            Aggregates shown for the first {formatNumber(posts.length)} posts — export for the full dataset
          </p>
        ) : null}
      </CardHeader>
      <CardContent>
        {error ? (
          <ApiErrorBanner title="Could not load results" message={error} onRetry={onRetry} />
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
            {loading
              ? Array.from({ length: 7 }).map((_, index) => (
                  <div key={index} className="animate-pulse rounded-xl border bg-card p-4">
                    <div className="h-8 w-8 rounded-lg bg-muted-foreground/15" />
                    <div className="mt-3 h-6 w-14 rounded bg-muted-foreground/15" />
                    <div className="mt-2 h-3 w-20 rounded bg-muted-foreground/10" />
                  </div>
                ))
              : kpis.map((kpi) => (
                  <div key={kpi.label} className="rounded-xl border bg-card p-4 transition-colors hover:bg-muted/40">
                    <div className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${ICON_TONES[kpi.tone] ?? ICON_TONES.blue}`}>
                      <kpi.icon className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <p className="mt-3 truncate text-xl font-bold tabular-nums leading-6">{kpi.value}</p>
                    <p className="mt-0.5 text-xs font-medium text-foreground/80">{kpi.label}</p>
                    <p className="truncate text-[11px] text-muted-foreground" title={kpi.caption}>
                      {kpi.caption}
                    </p>
                  </div>
                ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}