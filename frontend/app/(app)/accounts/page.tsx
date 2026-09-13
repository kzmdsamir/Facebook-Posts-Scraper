"use client";

import { useCallback, useEffect, useState } from "react";
import { KeyRound, RefreshCw, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { AccountSession } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function AccountsPage() {
  const [items, setItems] = useState<AccountSession[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listAccounts();
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load saved sessions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDelete = useCallback(
    async (name: string) => {
      setDeleting(name);
      setError(null);
      try {
        await api.deleteAccount(name);
        await load();
      } catch (e) {
        setError(e instanceof Error ? e.message : `Could not remove "${name}"`);
      } finally {
        setDeleting(null);
      }
    },
    [load],
  );

  return (
    <div className="animate-fade-in-up space-y-6">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>Saved sessions</CardTitle>
            <CardDescription className="mt-1">
              Cookie sessions created through the CLI login flow. Only metadata is shown here; cookie contents are never
              exposed.
            </CardDescription>
          </div>
          <span className="text-xs text-muted-foreground">{total} saved</span>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="flex items-center justify-between gap-3 rounded-sm border border-border bg-muted/40 px-3 py-2.5 text-sm">
              <span className="text-muted-foreground">{error}</span>
              <button
                type="button"
                onClick={() => void load()}
                className="flex items-center gap-1.5 rounded-sm border border-border px-2 py-1 text-xs transition-colors hover:text-foreground"
              >
                <RefreshCw className="h-3 w-3" strokeWidth={1.75} /> retry
              </button>
            </div>
          ) : null}

          {!error && loading && items.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">loading sessions…</p>
          ) : null}

          {!error && !loading && items.length === 0 ? (
            <div className="py-10 text-center">
              <KeyRound className="mx-auto h-6 w-6 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
              <p className="mt-3 text-sm text-muted-foreground">
                No saved sessions. Log the browser in once to speed up public scrapes:
              </p>
              <p className="mt-2 text-xs text-zinc-600">
                <code className="rounded-sm bg-muted px-2 py-1">python -m backend.scraper.browser_scraper --login --account name</code>
              </p>
            </div>
          ) : null}

          {items.length > 0 ? (
            <ul className="divide-y divide-border">
              {items.map((account) => (
                <li key={account.name} className="flex items-center gap-4 py-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm border border-border text-muted-foreground">
                    <KeyRound className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{account.name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {account.cookies_file ?? "session"}
                      {account.saved_at ? ` · saved ${formatDateTime(account.saved_at)}` : ""}
                    </p>
                  </div>
                  {account.name === "default" ? (
                    <span className="text-xs text-zinc-600">default</span>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void handleDelete(account.name)}
                    disabled={deleting === account.name}
                    className="flex items-center gap-1.5 rounded-sm border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-foreground/40 hover:text-foreground disabled:opacity-50"
                  >
                    <Trash2 className="h-3 w-3" strokeWidth={1.75} aria-hidden="true" />
                    {deleting === account.name ? "removing…" : "remove"}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}