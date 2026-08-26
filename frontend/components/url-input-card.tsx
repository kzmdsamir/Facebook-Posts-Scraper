"use client";

import { useMemo, useState } from "react";
import { CircleCheck, CircleX, Info, Play, Plus, RotateCcw, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { isFacebookUrl } from "@/lib/api";
import type { PostType, ScrapeRequest } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface ParsedUrl {
  raw: string;
  normalized: string | null;
  valid: boolean;
  reason: string | null;
}

export interface UrlInputCardProps {
  /** Lock all inputs while a job is running. */
  disabled?: boolean;
  submitting?: boolean;
  onSubmit: (request: ScrapeRequest) => void;
}

const POST_TYPE_OPTIONS: ReadonlyArray<{ value: "" | PostType; label: string }> = [
  { value: "", label: "All post types" },
  { value: "text", label: "Text" },
  { value: "image", label: "Image" },
  { value: "video", label: "Video / Reel" },
  { value: "link", label: "Link" },
];

export function UrlInputCard({ disabled = false, submitting = false, onSubmit }: UrlInputCardProps) {
  const [bulk, setBulk] = useState("");
  const [extras, setExtras] = useState<string[]>([""]);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [maxPosts, setMaxPosts] = useState("");
  const [postType, setPostType] = useState<"" | PostType>("");

  const parsedUrls = useMemo<ParsedUrl[]>(() => {
    const seen = new Set<string>();
    const output: ParsedUrl[] = [];
    const rows = [...bulk.split(/\r?\n/), ...extras];
    for (const row of rows) {
      const raw = row.trim();
      if (!raw) continue;
      const key = raw.toLowerCase();
      if (seen.has(key)) continue; // dedupe identical lines
      seen.add(key);
      output.push({ raw, ...isFacebookUrl(raw) });
    }
    return output;
  }, [bulk, extras]);

  const validCount = parsedUrls.filter((entry) => entry.valid).length;
  const invalidCount = parsedUrls.length - validCount;
  const duplicatedCount = useMemo(() => {
    const seen = new Set<string>();
    let dupes = 0;
    for (const row of [...bulk.split(/\r?\n/), ...extras]) {
      const key = row.trim().toLowerCase();
      if (!key) continue;
      if (seen.has(key)) dupes += 1;
      seen.add(key);
    }
    return dupes;
  }, [bulk, extras]);

  const dateRangeInvalid = startDate !== "" && endDate !== "" && startDate > endDate;
  const canSubmit = validCount > 0 && !dateRangeInvalid && !disabled && !submitting;

  const clearAll = () => {
    setBulk("");
    setExtras([""]);
    setStartDate("");
    setEndDate("");
    setMaxPosts("");
    setPostType("");
  };

  const handleSubmit = () => {
    if (!canSubmit) return;
    const urls = parsedUrls
      .filter((entry): entry is ParsedUrl & { normalized: string } => entry.valid && entry.normalized !== null)
      .map((entry) => entry.normalized);
    const parsedMax = Number.parseInt(maxPosts, 10);
    onSubmit({
      urls,
      max_posts: Number.isFinite(parsedMax) && parsedMax > 0 ? parsedMax : null,
      start_date: startDate === "" ? null : startDate,
      end_date: endDate === "" ? null : endDate,
      post_type: postType === "" ? null : postType,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Start a new scrape</CardTitle>
        <CardDescription>
          Paste public Facebook page or profile URLs, tune the filters, then start the job. Requests are throttled and
          only publicly available content is processed.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* URLs */}
        <div className="space-y-3">
          <label htmlFor="bulk-urls" className="text-sm font-medium">
            Facebook page / profile URLs <span className="text-muted-foreground">(one per line)</span>
          </label>
          <Textarea
            id="bulk-urls"
            value={bulk}
            onChange={(event) => setBulk(event.target.value)}
            placeholder={"https://www.facebook.com/examplepage\nhttps://www.facebook.com/examplepage2"}
            disabled={disabled}
            rows={4}
          />

          <div className="space-y-2">
            {extras.map((value, index) => (
              <div key={index} className="flex items-center gap-2">
                <Input
                  value={value}
                  onChange={(event) => {
                    const next = [...extras];
                    next[index] = event.target.value;
                    setExtras(next);
                  }}
                  placeholder={`Additional URL ${index + 1} (optional)`}
                  aria-label={`Additional URL ${index + 1}`}
                  disabled={disabled}
                  className="h-9"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 shrink-0"
                  onClick={() => setExtras((current) => current.filter((_, i) => i !== index))}
                  disabled={disabled || extras.length <= 1}
                  aria-label={`Remove additional URL ${index + 1}`}
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setExtras((current) => [...current, ""])}
              disabled={disabled}
            >
              <Plus className="h-4 w-4" aria-hidden="true" /> Add another URL
            </Button>
          </div>

          {/* Validation hints */}
          {parsedUrls.length > 0 ? (
            <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant={validCount > 0 ? "success" : "destructive"}>
                  {validCount} valid
                </Badge>
                {invalidCount > 0 ? <Badge variant="destructive">{invalidCount} invalid</Badge> : null}
                {duplicatedCount > 0 ? <Badge variant="secondary">{duplicatedCount} duplicate line{duplicatedCount === 1 ? "" : "s"} ignored</Badge> : null}
                {invalidCount > 0 ? (
                  <span className="flex items-center gap-1 text-xs">
                    <Info className="h-3 w-3" aria-hidden="true" /> Invalid URLs are skipped when starting.
                  </span>
                ) : null}
              </div>
              <ul className="max-h-40 space-y-1 overflow-y-auto pr-1">
                {parsedUrls.map((entry, index) => (
                  <li key={`${entry.raw}-${index}`} className="flex items-start gap-2 text-xs">
                    {entry.valid ? (
                      <CircleCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" aria-hidden="true" />
                    ) : (
                      <CircleX className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" aria-hidden="true" />
                    )}
                    <span className={cn("min-w-0 break-all", entry.valid ? "text-foreground" : "text-muted-foreground line-through")}>
                      {entry.raw}
                      {entry.valid ? null : <span className="not-italic text-destructive"> — {entry.reason}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        {/* Configuration */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1.5">
            <label htmlFor="date-start" className="text-sm font-medium">Start date</label>
            <Input id="date-start" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} disabled={disabled} />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="date-end" className="text-sm font-medium">End date</label>
            <Input id="date-end" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} disabled={disabled} />
            {dateRangeInvalid ? (
              <p className="text-xs text-destructive" role="alert">End date must be on or after start date.</p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <label htmlFor="max-posts" className="text-sm font-medium">Maximum posts</label>
            <Input
              id="max-posts"
              type="number"
              min={1}
              step={1}
              value={maxPosts}
              onChange={(event) => setMaxPosts(event.target.value)}
              placeholder="No limit"
              disabled={disabled}
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="post-type" className="text-sm font-medium">Post type</label>
            <Select id="post-type" value={postType} onChange={(event) => setPostType(event.target.value as "" | PostType)} disabled={disabled}>
              {POST_TYPE_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            {disabled ? (
              <p className="text-xs text-muted-foreground">Scraping in progress — inputs are locked until the job finishes.</p>
            ) : (
              <Button type="button" variant="ghost" size="sm" onClick={clearAll} disabled={submitting}>
                <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" /> Clear
              </Button>
            )}
          </div>
          <Button type="button" size="lg" onClick={handleSubmit} disabled={!canSubmit} loading={submitting} className="w-full sm:w-auto">
            <Play className="h-4 w-4" aria-hidden="true" />
            {submitting ? "Starting…" : "Start Scraping"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}