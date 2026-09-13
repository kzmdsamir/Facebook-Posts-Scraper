"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { useTheme } from "@/components/theme-provider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  readScrapeDefaults,
  writeScrapeDefaults,
  type ScrapeDefaults,
} from "@/lib/settings";
import { cn } from "@/lib/utils";

const POST_TYPE_OPTIONS: ReadonlyArray<{ value: ScrapeDefaults["postType"]; label: string }> = [
  { value: "", label: "All post types" },
  { value: "text", label: "Text" },
  { value: "image", label: "Image" },
  { value: "video", label: "Video / Reel" },
  { value: "link", label: "Link" },
];

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [defaults, setDefaults] = useState<ScrapeDefaults | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setDefaults(readScrapeDefaults());
  }, []);

  const update = (patch: Partial<ScrapeDefaults>) => {
    if (!defaults) return;
    const next = { ...defaults, ...patch };
    setDefaults(next);
    writeScrapeDefaults(next);
    setSaved(true);
  };

  return (
    <div className="animate-fade-in-up space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription className="mt-1">Dark is the terminal default; light is fully supported.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            {(
              [
                { value: "dark", label: "Dark" },
                { value: "light", label: "Light" },
              ] as const
            ).map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setTheme(option.value)}
                aria-pressed={theme === option.value}
                className={cn(
                  "flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors",
                  theme === option.value
                    ? "border-foreground bg-foreground text-background"
                    : "border-border text-muted-foreground hover:bg-muted",
                )}
              >
                {theme === option.value ? <Check className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" /> : null}
                {option.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Default scrape options</CardTitle>
          <CardDescription className="mt-1">
            Prefills the "New scrape" form. Stored locally in this browser; overridable per run.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {defaults === null ? (
            <p className="text-sm text-muted-foreground">loading…</p>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <label htmlFor="set-max-posts" className="text-sm font-medium">Maximum posts</label>
                  <Input
                    id="set-max-posts"
                    type="number"
                    min={1}
                    step={1}
                    value={defaults.maxPosts}
                    placeholder="No limit"
                    onChange={(event) => update({ maxPosts: event.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="set-post-type" className="text-sm font-medium">Post type</label>
                  <Select
                    id="set-post-type"
                    value={defaults.postType}
                    onChange={(event) => update({ postType: event.target.value as ScrapeDefaults["postType"] })}
                  >
                    {POST_TYPE_OPTIONS.map((option) => (
                      <option key={option.value || "all"} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="set-scrolls" className="text-sm font-medium">Scroll rounds</label>
                  <Input
                    id="set-scrolls"
                    type="number"
                    min={1}
                    max={300}
                    step={1}
                    value={defaults.scrolls}
                    placeholder="40"
                    onChange={(event) => update({ scrolls: event.target.value })}
                  />
                </div>
              </div>

              <label className="flex w-fit cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={defaults.useBrowser}
                  onChange={(event) => update({ useBrowser: event.target.checked })}
                  className="mt-0.5 h-4 w-4 accent-foreground"
                />
                <span className="space-y-1">
                  <span className="block text-sm font-medium">Browser mode by default</span>
                  <span className="block text-xs text-muted-foreground">
                    Scrape the page's own GraphQL feed via Playwright instead of the static HTML fallback.
                  </span>
                </span>
              </label>

              <p className="text-xs text-muted-foreground">
                {saved ? "Saved ✓" : "Changes save immediately."}
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}