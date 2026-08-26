"use client";

import { FileJson, FileSpreadsheet, RotateCcw, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { ExportFormat, JobStatus } from "@/lib/types";
import { EXPORT_FILENAMES } from "@/lib/types";

export interface ExportAreaProps {
  jobId: string | null;
  status: JobStatus | null;
  onNewScrape: () => void;
}

const FORMATS: Array<{
  format: ExportFormat;
  title: string;
  description: string;
  icon: typeof FileJson;
  tone: string;
}> = [
  { format: "json", title: "JSON", description: "Complete nested structure", icon: FileJson, tone: "text-emerald-500" },
  { format: "csv", title: "CSV", description: "Flattened spreadsheet", icon: FileText, tone: "text-sky-500" },
  { format: "excel", title: "Excel", description: "XLSX workbook, multiple sheets", icon: FileSpreadsheet, tone: "text-emerald-600 dark:text-emerald-400" },
];

export function ExportArea({ jobId, status, onNewScrape }: ExportAreaProps) {
  if (!jobId || (status !== "completed" && status !== "failed")) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Export results</CardTitle>
        <CardDescription>
          Downloads are generated live by the backend from the stored job results.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {FORMATS.map((entry) => (
            <a
              key={entry.format}
              href={api.getExportUrl(jobId, entry.format)}
              download={EXPORT_FILENAMES[entry.format]}
              className="group rounded-xl border bg-card p-4 transition-colors hover:border-primary/50 hover:bg-muted/40"
            >
              <div className="flex items-center gap-3">
                <entry.icon className={`h-6 w-6 ${entry.tone}`} aria-hidden="true" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold">↓ {entry.title}</p>
                  <p className="truncate text-xs text-muted-foreground">{entry.description}</p>
                </div>
              </div>
              <p className="mt-3 truncate font-mono text-[11px] text-muted-foreground">{EXPORT_FILENAMES[entry.format]}</p>
            </a>
          ))}
        </div>
        <div className="flex flex-col-reverse items-start justify-between gap-3 border-t pt-4 sm:flex-row sm:items-center">
          <p className="text-xs text-muted-foreground">
            Job <code className="rounded bg-muted px-1.5 py-0.5 font-mono">{jobId}</code>
          </p>
          <Button type="button" variant="outline" onClick={onNewScrape}>
            <RotateCcw className="h-4 w-4" aria-hidden="true" /> New scrape
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}