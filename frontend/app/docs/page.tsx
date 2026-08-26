import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, FileJson, FileSpreadsheet, FileText, Scale, ShieldCheck, Timer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Documentation",
  description: "Permitted use, compliance notes and API reference for the Facebook Posts Scraper.",
};

const ENDPOINTS: Array<{ method: string; path: string; description: string }> = [
  { method: "POST", path: "/api/scrape", description: "Start a scraping job. Body: { urls: string[], max_posts?, start_date?, end_date?, post_type? } → { job_id, status }" },
  { method: "GET", path: "/api/jobs/{job_id}", description: "Job status, progress counters (pages_total, pages_completed, posts_found, posts_processed, duplicates, errors) and error_details." },
  { method: "GET", path: "/api/jobs/{job_id}/posts", description: "Paginated normalized posts. Query: page, page_size. Response: { items, total, page, page_size }." },
  { method: "GET", path: "/api/jobs/{job_id}/export/json", description: "Full nested JSON export (streamed download)." },
  { method: "GET", path: "/api/jobs/{job_id}/export/csv", description: "Flattened CSV export." },
  { method: "GET", path: "/api/jobs/{job_id}/export/excel", description: "Excel workbook (XLSX) with Posts / Engagement / Media / Metadata sheets." },
  { method: "DELETE", path: "/api/jobs/{job_id}", description: "Delete a job and its stored results. Returns 204." },
];

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-muted/30">
        <div className="mx-auto flex h-16 w-full max-w-4xl items-center gap-3 px-4 sm:px-6">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.svg" alt="Facebook Posts Scraper logo" className="h-8 w-8 rounded-lg" />
          <p className="text-base font-semibold">Facebook Posts Scraper — Documentation</p>
          <Link href="/" className="ml-auto inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to dashboard
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl space-y-6 px-4 py-8 sm:px-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-500" aria-hidden="true" /> Permitted use & compliance
            </CardTitle>
            <CardDescription>Read this before running scrapes. Violations can get you — and the site you scrape — into trouble.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm leading-relaxed text-muted-foreground">
            <p>
              The scraper targets <strong className="text-foreground">publicly available</strong> posts published by Facebook pages and
              profiles. It does not log in, does not answer CAPTCHAs, does not rotate identities, and never tries to reach content behind
              authentication or privacy controls. Requests are throttled and time-boxed.
            </p>
            <ul className="list-disc space-y-1 pl-5">
              <li>Only enter URLs you are authorized to access.</li>
              <li>Respect Facebook/Meta’s Terms of Service, robots/access restrictions and applicable laws (including data-protection rules).</li>
              <li>Do not republish personal data without a lawful basis.</li>
              <li>Facebook can change its public HTML at any time; extraction may fail gracefully per-URL — that is expected behavior.</li>
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Scale className="h-5 w-5 text-sky-500" aria-hidden="true" /> How the dashboard works
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal space-y-1.5 pl-5 text-sm leading-relaxed text-muted-foreground">
              <li>Enter page/profile URLs (paste many at once or add them one by one). Invalid URLs are flagged client-side before you submit.</li>
              <li>Optionally narrow the scrape: date range, maximum number of posts, post type (Text / Image / Video-Reel / Link).</li>
              <li>The backend creates a job; the dashboard polls <code className="rounded bg-muted px-1 font-mono text-xs">GET /api/jobs/&#123;id&#125;</code> every 1.5&nbsp;s and renders a live progress bar with counters.</li>
              <li>When the job completes, up to 2,000 posts are loaded into the browser for preview — search, sort, paginate, and open the full detail view by clicking a row.</li>
              <li>Download the complete dataset as JSON, CSV or Excel. Exports are generated server-side and streamed; large datasets should use the exports rather than the on-screen preview.</li>
            </ol>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileJson className="h-5 w-5 text-emerald-500" aria-hidden="true" />
              <FileSpreadsheet className="h-5 w-5 text-emerald-500" aria-hidden="true" />
              <FileText className="h-5 w-5 text-emerald-500" aria-hidden="true" />
              <span>API reference</span>
            </CardTitle>
            <CardDescription>
              Base URL: <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">http://localhost:8000</code> (override with the{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">NEXT_PUBLIC_API_URL</code> environment variable at build time).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-medium">Method</th>
                    <th className="px-3 py-2 font-medium">Path</th>
                    <th className="hidden px-3 py-2 font-medium md:table-cell">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {ENDPOINTS.map((endpoint) => (
                    <tr key={`${endpoint.method}-${endpoint.path}`}>
                      <td className="px-3 py-2.5">
                        <Badge
                          variant={
                            endpoint.method === "GET"
                              ? "blue"
                              : endpoint.method === "POST"
                                ? "success"
                                : endpoint.method === "DELETE"
                                  ? "destructive"
                                  : "secondary"
                          }
                        >
                          {endpoint.method}
                        </Badge>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 font-mono text-xs">{endpoint.path}</td>
                      <td className="hidden px-3 py-2.5 text-xs text-muted-foreground md:table-cell">{endpoint.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Timer className="h-3.5 w-3.5" aria-hidden="true" />
              Errors use the shape <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">&#123; "error": &#123; "code": string, "message": string &#125; &#125;</code>.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Export formats</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p><strong className="text-foreground">JSON</strong> — complete nested structure (identity, content, engagement, media, links). Best for machine processing.</p>
            <p><strong className="text-foreground">CSV</strong> — one row per post, flattened (post_id, page_name, post_url, published_at, text, post_type, likes, comments, shares, views, thumbnails…). Best for spreadsheets.</p>
            <p><strong className="text-foreground">Excel (.xlsx)</strong> — formatted workbook with separate <em>Posts</em>, <em>Engagement</em>, <em>Media</em> and <em>Metadata</em> sheets, frozen header rows and column filters.</p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}