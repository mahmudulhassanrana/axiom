"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Source } from "@/lib/sources-types";
import { SourcesTable } from "./sources-table";

export function SourcesListPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const data = await apiFetch<Source[]>("/sources");
      setSources(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load sources");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
          Sources are reusable scrape targets. Configure crawl depth, delays, and optional schedules, then enqueue jobs
          with one click.
        </p>
        <Link
          href="/sources/new"
          className="inline-flex shrink-0 items-center justify-center rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white shadow-glow hover:bg-accent-hover"
        >
          New source
        </Link>
      </div>

      {error ? (
        <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          <strong className="font-medium">API:</strong> {error}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-border-subtle bg-surface-raised/50 px-6 py-10 text-center text-sm text-slate-500">
          Loading sources…
        </div>
      ) : (
        <SourcesTable sources={sources} />
      )}
    </div>
  );
}
