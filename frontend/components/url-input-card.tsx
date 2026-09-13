"use client";

import { useEffect, useMemo, useState } from "react";
import { CircleCheck, CircleX, Play, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, isFacebookUrl } from "@/lib/api";
import { readScrapeDefaults } from "@/lib/settings";
import type { AccountSession, PostType, ScrapeRequest } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";

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
  /** Seed the targets textarea (e.g. a URL piped in from the Home screen). */
  initialUrls?: string;
  onSubmit: (request: ScrapeRequest) => void;
  /** Called when the user edits the form, so a stale start error can clear. */
  onClearError?: () => void;
}

type TimePreset = "" | "7d" | "30d" | "90d" | "1y" | "custom";

const POST_TYPE_OPTIONS: ReadonlyArray<{ value: "" | PostType; label: string }> = [
  { value: "", label: "All post types" },
  { value: "text", label: "Text" },
  { value: "image", label: "Image" },
  { value: "video", label: "Video / Reel" },
  { value: "link", label: "Link" },
];

const TIME_FRAME_OPTIONS: ReadonlyArray<{ value: TimePreset; label: string }> = [
  { value: "", label: "All time" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "1y", label: "Last year" },
  { value: "custom", label: "Custom" },
];

const SCROLL_ROUND_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "", label: "Auto (stop when no new posts)" },
  { value: "10", label: "10 rounds" },
  { value: "20", label: "20 rounds" },
  { value: "40", label: "40 rounds" },
  { value: "60", label: "60 rounds" },
  { value: "100", label: "100 rounds" },
  { value: "200", label: "200 rounds" },
  { value: "300", label: "300 rounds (max)" },
];

const FIELD_INPUT_CLASS =
  "h-9 rounded-none border border-black bg-white font-sans text-sm tracking-normal text-black placeholder:text-neutral-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-400";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-400">{children}</p>
  );
}

function FieldLabel({ htmlFor, children }: { htmlFor?: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block font-sans text-xs font-medium normal-case text-neutral-700">
      {children}
    </label>
  );
}

/** Rectangular segmented control — active is solid black, inactive white. */
function ToggleGroup<T extends string>({
  value,
  options,
  onChange,
  disabled,
  ariaLabel,
}: {
  value: T;
  options: ReadonlyArray<{ value: T; label: string }>;
  onChange: (value: T) => void;
  disabled?: boolean;
  ariaLabel: string;
}) {
  return (
    <div role="group" aria-label={ariaLabel} className="flex flex-wrap">
      {options.map((option, index) => {
        const active = value === option.value;
        return (
          <button
            key={option.value || "none"}
            type="button"
            onClick={() => onChange(option.value)}
            disabled={disabled}
            aria-pressed={active}
            className={cn(
              "-ml-px border px-3 py-1.5 font-sans text-xs font-medium normal-case transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-400 first:ml-0",
              index > 0 && "-ml-px",
              active
                ? "border-black bg-black text-white"
                : "border-neutral-200 bg-white text-neutral-500 hover:border-black hover:text-black"
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function UrlInputCard({
  disabled = false,
  submitting = false,
  initialUrls,
  onSubmit,
  onClearError,
}: UrlInputCardProps) {
  const [bulk, setBulk] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [maxPosts, setMaxPosts] = useState("");
  const [postType, setPostType] = useState<"" | PostType>("");
  const [useBrowser, setUseBrowser] = useState(false);
  const [account, setAccount] = useState("");
  const [scrolls, setScrolls] = useState("");
  const [timeFrame, setTimeFrame] = useState<TimePreset>("");
  const [accounts, setAccounts] = useState<AccountSession[]>([]);

  // Prefill persisted default options ("Settings → Default scrape options").
  useEffect(() => {
    const saved = readScrapeDefaults();
    if (saved.maxPosts) setMaxPosts(saved.maxPosts);
    if (saved.postType) setPostType(saved.postType);
    if (saved.scrolls) setScrolls(saved.scrolls);
    if (saved.useBrowser) setUseBrowser(true);
  }, []);

  // Load the saved sessions for the account dropdown.
  useEffect(() => {
    let cancelled = false;
    api
      .listAccounts()
      .then((res) => {
        if (!cancelled) setAccounts(res.items);
      })
      .catch(() => {
        // Backend unreachable — dropdown just stays on "anonymous".
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // A URL piped in from the Home screen lands in the targets box.
  useEffect(() => {
    if (initialUrls) setBulk(initialUrls);
  }, [initialUrls]);

  const setPresetDates = (preset: TimePreset) => {
    setTimeFrame(preset);
    if (preset === "" || preset === "custom") {
      setStartDate("");
      setEndDate("");
      return;
    }
    const days = preset === "7d" ? 7 : preset === "30d" ? 30 : preset === "90d" ? 90 : 365;
    const today = new Date();
    const start = new Date(today.getTime() - days * 86400000);
    setStartDate(start.toISOString().slice(0, 10));
    setEndDate(today.toISOString().slice(0, 10));
  };

  const parsedUrls = useMemo<ParsedUrl[]>(() => {
    const seen = new Set<string>();
    const output: ParsedUrl[] = [];
    for (const row of bulk.split(/\r?\n/)) {
      const raw = row.trim();
      if (!raw) continue;
      const key = raw.toLowerCase();
      if (seen.has(key)) continue; // dedupe identical lines
      seen.add(key);
      output.push({ raw, ...isFacebookUrl(raw) });
    }
    return output;
  }, [bulk]);

  const validCount = parsedUrls.filter((entry) => entry.valid).length;
  const invalidCount = parsedUrls.length - validCount;
  const duplicatedCount = useMemo(() => {
    const seen = new Set<string>();
    let dupes = 0;
    for (const row of bulk.split(/\r?\n/)) {
      const key = row.trim().toLowerCase();
      if (!key) continue;
      if (seen.has(key)) dupes += 1;
      seen.add(key);
    }
    return dupes;
  }, [bulk]);

  const dateRangeInvalid = startDate !== "" && endDate !== "" && startDate > endDate;
  const isCustomDate = timeFrame === "custom";
  const canSubmit = validCount > 0 && !dateRangeInvalid && !disabled && !submitting;
  const scrollOptions = useMemo(() => {
    const hasCustom = scrolls !== "" && !SCROLL_ROUND_OPTIONS.some((option) => option.value === scrolls);
    return hasCustom
      ? [...SCROLL_ROUND_OPTIONS, { value: scrolls, label: `${scrolls} rounds (custom)` }]
      : SCROLL_ROUND_OPTIONS;
  }, [scrolls]);

  const clearAll = () => {
    setBulk("");
    setStartDate("");
    setEndDate("");
    setMaxPosts("");
    setPostType("");
    setUseBrowser(false);
    setAccount("");
    setScrolls("");
    setTimeFrame("");
  };

  const handleSubmit = () => {
    if (!canSubmit) return;
    const urls = parsedUrls
      .filter((entry): entry is ParsedUrl & { normalized: string } => entry.valid && entry.normalized !== null)
      .map((entry) => entry.normalized);
    const parsedMax = Number.parseInt(maxPosts, 10);
    const parsedScrolls = Number.parseInt(scrolls, 10);
    onSubmit({
      urls,
      max_posts: Number.isFinite(parsedMax) && parsedMax > 0 ? parsedMax : null,
      start_date: startDate === "" ? null : startDate,
      end_date: endDate === "" ? null : endDate,
      post_type: postType === "" ? null : postType,
      use_browser: useBrowser,
      account: useBrowser && account.trim() !== "" ? account.trim() : null,
      scrolls: useBrowser && Number.isFinite(parsedScrolls) && parsedScrolls > 0 ? parsedScrolls : null,
    });
  };

  return (
    <div className="mx-auto w-full max-w-5xl">
      {/* Targets */}
      <div>
        <Eyebrow>Targets</Eyebrow>
        <textarea
          id="bulk-urls"
          value={bulk}
          onChange={(event) => {
            setBulk(event.target.value);
            onClearError?.();
          }}
          placeholder={"https://www.facebook.com/examplepage"}
          disabled={disabled}
          rows={4}
          className="mt-2 w-full resize-y rounded-none border border-black bg-white p-4 font-mono text-sm tracking-normal text-black placeholder:text-neutral-400 focus:outline-none focus:ring-0"
        />
        <p className="mt-2 font-mono text-[10px] uppercase tracking-widest text-neutral-400">
          Paste one Facebook public page or profile URL per line
        </p>

        {/* Validation */}
        {parsedUrls.length > 0 ? (
          <div className="mt-4">
            <p className="font-sans text-xs text-neutral-500">
              {validCount > 0 ? <span className="text-green-700">{`${validCount} valid`}</span> : null}
              {invalidCount > 0 ? (
                <span className="text-red-700">{` · ${invalidCount} invalid`}</span>
              ) : null}
              {duplicatedCount > 0 ? ` · ${duplicatedCount} duplicate line${duplicatedCount === 1 ? "" : "s"} ignored` : ""}
            </p>
            <ul className="mt-1.5 max-h-40 space-y-1 overflow-y-auto">
              {parsedUrls.map((entry, index) => (
                <li key={`${entry.raw}-${index}`} className="flex items-start gap-2 font-mono text-xs">
                  {entry.valid ? (
                    <CircleCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-700" aria-hidden="true" />
                  ) : (
                    <CircleX className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-700" aria-hidden="true" />
                  )}
                  <span className={cn("min-w-0 break-all", entry.valid ? "text-neutral-800" : "text-neutral-400 line-through")}>
                    {entry.raw}
                    {entry.valid ? null : <span className="text-red-700 not-italic">, {entry.reason}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      {/* Configuration */}
      <div className="mt-8">
        <Eyebrow>Configuration · Filters</Eyebrow>

        <div className="mt-3">
          <FieldLabel htmlFor="time-frame">Time frame</FieldLabel>
          <ToggleGroup
            value={timeFrame}
            options={TIME_FRAME_OPTIONS}
            onChange={setPresetDates}
            disabled={disabled}
            ariaLabel="Time frame"
          />
          <p className="mt-1.5 font-sans text-xs text-neutral-500">
            {dateRangeInvalid
              ? "End date must be on or after start date."
              : isCustomDate
                ? startDate === "" && endDate === ""
                  ? "Pick a start and end date"
                  : `${startDate || "…"} → ${endDate || "…"}`
                : startDate === "" && endDate === ""
                  ? "No date filter (default)"
                  : `${startDate || "…"} → ${endDate || "…"}`}
          </p>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {isCustomDate ? (
            <>
              <div>
                <FieldLabel htmlFor="date-start">Start date</FieldLabel>
                <Input
                  id="date-start"
                  type="date"
                  value={startDate}
                  onChange={(event) => {
                    setStartDate(event.target.value);
                    setTimeFrame("custom");
                  }}
                  disabled={disabled}
                  className={FIELD_INPUT_CLASS}
                />
              </div>
              <div>
                <FieldLabel htmlFor="date-end">End date</FieldLabel>
                <Input
                  id="date-end"
                  type="date"
                  value={endDate}
                  onChange={(event) => {
                    setEndDate(event.target.value);
                    setTimeFrame("custom");
                  }}
                  disabled={disabled}
                  className={FIELD_INPUT_CLASS}
                />
              </div>
            </>
          ) : null}
          <div>
            <FieldLabel htmlFor="max-posts">Maximum posts</FieldLabel>
            <Input
              id="max-posts"
              type="number"
              min={1}
              step={1}
              value={maxPosts}
              onChange={(event) => setMaxPosts(event.target.value)}
              placeholder="No limit"
              disabled={disabled}
              className={FIELD_INPUT_CLASS}
            />
          </div>
          <div>
            <FieldLabel htmlFor="post-type">Post type</FieldLabel>
            <Select
              id="post-type"
              value={postType}
              onChange={(event) => setPostType(event.target.value as "" | PostType)}
              disabled={disabled}
              className={FIELD_INPUT_CLASS}
            >
              {POST_TYPE_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {/* Browser mode */}
        <div className="mt-8">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={useBrowser}
              onChange={(event) => setUseBrowser(event.target.checked)}
              disabled={disabled}
              className="mt-0.5 h-4 w-4 accent-black"
            />
            <span className="space-y-0.5">
              <span className="block font-sans text-xs font-medium text-neutral-900">Browser Mode (Playwright)</span>
              <span className="block font-sans text-xs leading-relaxed text-neutral-500">
                Scrapes the page's own GraphQL feed and scrolls to load more posts.
              </span>
            </span>
          </label>

          {useBrowser ? (
            <div className="mt-4 grid grid-cols-1 gap-4 pl-7 sm:grid-cols-2">
              <div>
                <FieldLabel htmlFor="account-name">Saved account (cookies)</FieldLabel>
                <Select
                  id="account-name"
                  value={account}
                  onChange={(event) => setAccount(event.target.value)}
                  disabled={disabled}
                  className={FIELD_INPUT_CLASS}
                >
                  <option value="">Anonymous (no saved session)</option>
                  {accounts.map((entry) => (
                    <option key={entry.name} value={entry.name}>
                      {entry.name}
                      {entry.saved_at ? ` · saved ${formatDateTime(entry.saved_at)}` : ""}
                    </option>
                  ))}
                </Select>
                <p className="mt-1.5 font-sans text-xs leading-relaxed text-neutral-500">
                  Cookies unlock the full feed; anonymous sessions are capped by Facebook. Add more with {" "}
                  <code className="font-mono">python cli.py login --account NAME</code>.
                </p>
              </div>
              <div>
                <FieldLabel htmlFor="scroll-count">Scroll rounds</FieldLabel>
                <Select
                  id="scroll-count"
                  value={scrolls}
                  onChange={(event) => setScrolls(event.target.value)}
                  disabled={disabled}
                  className={FIELD_INPUT_CLASS}
                >
                  {scrollOptions.map((option) => (
                    <option key={option.value || "auto"} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Action bar */}
      <div className="mt-8 flex flex-col-reverse items-stretch justify-between gap-4 border-t border-neutral-200 pt-6 sm:flex-row sm:items-center">
        {disabled ? (
          <p className="font-sans text-xs text-neutral-500">
            Scraping in progress, inputs are locked until the job finishes.
          </p>
        ) : (
          <Button
            type="button"
            variant="ghost"
            onClick={clearAll}
            disabled={submitting}
            className="justify-start rounded-none px-0 font-mono text-xs uppercase text-neutral-400 hover:bg-transparent hover:text-black"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" /> Clear
          </Button>
        )}
        <Button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          loading={submitting}
          className="h-12 w-full rounded-none bg-black px-8 py-3 font-mono text-xs uppercase tracking-widest text-white transition-colors hover:bg-neutral-800 sm:w-auto"
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {submitting ? "Starting…" : "Start Scraping"}
        </Button>
      </div>
    </div>
  );
}