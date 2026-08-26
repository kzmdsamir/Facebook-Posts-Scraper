"use client";

import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FileJson,
  FileSpreadsheet,
  FileText,
  Scale,
  ShieldCheck,
  Timer,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";

const ENDPOINTS: Array<{ method: string; path: string; description: string }> = [
  { method: "POST", path: "/api/scrape", description: "Start a scraping job: { urls[], max_posts?, start_date?, end_date?, post_type? }" },
  { method: "GET", path: "/api/jobs/{job_id}", description: "Job status + progress counters + error_details" },
  { method: "GET", path: "/api/jobs/{job_id}/posts", description: "Paginated normalized posts (?page & page_size)" },
  { method: "GET", path: "/api/jobs/{job_id}/export/json", description: "Download full nested JSON export" },
  { method: "GET", path: "/api/jobs/{job_id}/export/csv", description: "Download flattened CSV export" },
  { method: "GET", path: "/api/jobs/{job_id}/export/excel", description: "Download Excel workbook (XLSX)" },
  { method: "DELETE", path: "/api/jobs/{job_id}", description: "Delete a job and its stored results (204)" },
];

export function DocsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} title="Documentation & compliance" description="Quick help for the Facebook Posts Scraper dashboard" size="lg">
      <div className="space-y-6">
        <section className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4 text-emerald-500" aria-hidden="true" /> Permitted use
          </h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            <li>This tool extracts <strong className="text-foreground">publicly available</strong> posts from Facebook pages and profiles only.</li>
            <li>You may only scrape content you are authorized to access. Private profiles and auth-gated content are out of scope and never bypassed.</li>
            <li>Respect Facebook/Meta terms, robots/access restrictions and applicable laws; requests are throttled and run at human-like pace.</li>
            <li>Handle personal data carefully — treat exported data in line with your privacy obligations.</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden="true" /> What this tool does not do
          </h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            <li>No login bypass, no CAPTCHA solving, no anti-bot evasion, no private-profile access.</li>
            <li>No fabrication of data: fields Facebook does not expose are left empty (never invented).</li>
            <li>Pages may change at any time; scraping can fail gracefully per-URL without aborting the whole job.</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Scale className="h-4 w-4 text-sky-500" aria-hidden="true" /> How it works
          </h3>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Enter one or more public Facebook page/profile URLs and optional filters.</li>
            <li>The backend creates a job (<Badge variant="secondary">queued</Badge> → <Badge variant="secondary">running</Badge> → <Badge variant="success">completed</Badge> or <Badge variant="destructive">failed</Badge>).</li>
            <li>The dashboard polls progress every ~1.5s and shows live counters.</li>
            <li>Results are previewed in a searchable, sortable table; click any row for the full post.</li>
            <li>Download everything as JSON, CSV or Excel — exports stream straight from the backend.</li>
          </ol>
        </section>

        <section className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <FileJson className="h-4 w-4 text-emerald-500" aria-hidden="true" />
            <FileSpreadsheet className="h-4 w-4 text-emerald-500" aria-hidden="true" />
            <FileText className="h-4 w-4 text-emerald-500" aria-hidden="true" />
            <span>API reference</span>
          </h3>
          <div className="overflow-hidden rounded-lg border">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/60 text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Method</th>
                  <th className="px-3 py-2 font-medium">Path</th>
                  <th className="hidden px-3 py-2 font-medium sm:table-cell">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {ENDPOINTS.map((endpoint, index) => (
                  <tr key={`${endpoint.method}-${endpoint.path}-${index}`}>
                    <td className="px-3 py-2">
                      <Badge variant={endpoint.method === "GET" ? "blue" : endpoint.method === "POST" ? "success" : endpoint.method === "DELETE" ? "destructive" : "secondary"}>
                        {endpoint.method}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 font-mono text-foreground">{endpoint.path}</td>
                    <td className="hidden px-3 py-2 text-muted-foreground sm:table-cell">{endpoint.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Timer className="h-3.5 w-3.5" aria-hidden="true" /> API base: <code className="rounded bg-muted px-1 py-0.5 font-mono">NEXT_PUBLIC_API_URL</code> (default <code className="rounded bg-muted px-1 py-0.5 font-mono">http://localhost:8000</code>).
          </p>
        </section>

        <section className="flex items-center justify-between rounded-lg border bg-muted/40 px-4 py-3">
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-hidden="true" />
            Full documentation page available.
          </p>
          <Link
            href="/docs"
            onClick={onClose}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
          >
            Open full docs <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </section>
      </div>
    </Dialog>
  );
}