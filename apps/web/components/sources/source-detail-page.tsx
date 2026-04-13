"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { FormattedDate } from "@/components/formatted-date";
import { apiFetch } from "@/lib/api";
import type { SourceDetail, SourceRunResponse } from "@/lib/sources-types";

function statusPill(status: string) {
  const base =
    "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide";
  switch (status) {
    case "completed":
      return `${base} bg-emerald-950/80 text-emerald-300 ring-1 ring-emerald-800/60`;
    case "failed":
      return `${base} bg-red-950/80 text-red-300 ring-1 ring-red-900/60`;
    case "running":
      return `${base} bg-amber-950/80 text-amber-200 ring-1 ring-amber-800/60`;
    case "queued":
    case "pending":
      return `${base} bg-slate-800 text-slate-300 ring-1 ring-slate-700`;
    default:
      return `${base} bg-slate-800 text-slate-400 ring-1 ring-slate-700`;
  }
}

type Props = {
  sourceId: string;
};

export function SourceDetailPage({ sourceId }: Props) {
  const [detail, setDetail] = useState<SourceDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [runBusy, setRunBusy] = useState(false);
  const [runMsg, setRunMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const d = await apiFetch<SourceDetail>(`/sources/${sourceId}`);
      setDetail(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load source");
    } finally {
      setLoading(false);
    }
  }, [sourceId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runSource() {
    setRunBusy(true);
    setRunMsg(null);
    try {
      const res = await apiFetch<SourceRunResponse>(`/sources/${sourceId}/run`, { method: "POST" });
      setRunMsg(`Job ${res.job_id} queued (${res.status}). Open it from the table below.`);
      await load();
    } catch (e) {
      setRunMsg(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-border-subtle bg-surface-raised/50 px-6 py-10 text-center text-sm text-slate-500">
        Loading source…
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">
        {error ?? "Source not found"}
      </div>
    );
  }

  const lastJob = detail.recent_jobs[0];
  const lastStatus = lastJob?.last_run_status ?? lastJob?.status ?? "—";

  return (
    <div className="space-y-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{detail.name}</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">{detail.description || "No description."}</p>
          <p className="mt-2 font-mono text-xs text-slate-500 break-all">{detail.base_url}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={runBusy || !detail.is_active}
            onClick={() => void runSource()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white shadow-glow hover:bg-accent-hover disabled:opacity-50"
          >
            {runBusy ? "Starting…" : "Run source"}
          </button>
          <Link
            href={`/sources/${sourceId}/edit`}
            className="rounded-lg border border-border-subtle px-4 py-2 text-sm text-slate-200 hover:bg-surface-overlay"
          >
            Edit
          </Link>
          <Link href="/sources" className="rounded-lg border border-border-subtle px-4 py-2 text-sm text-slate-400 hover:bg-surface-overlay">
            All sources
          </Link>
        </div>
      </div>

      {runMsg ? <div className="text-sm text-slate-400">{runMsg}</div> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border-subtle bg-surface-raised/50 p-5 space-y-3 text-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Configuration</h3>
          <dl className="grid grid-cols-2 gap-2 text-slate-300">
            <dt className="text-slate-500">Crawl type</dt>
            <dd>{detail.crawl_type}</dd>
            <dt className="text-slate-500">Max pages</dt>
            <dd>{detail.max_pages}</dd>
            <dt className="text-slate-500">Delays</dt>
            <dd>
              {detail.delay_min} – {detail.delay_max}s
            </dd>
            <dt className="text-slate-500">External</dt>
            <dd>{detail.allow_external ? "Yes" : "No"}</dd>
            <dt className="text-slate-500">Engine</dt>
            <dd className="font-mono text-xs">{detail.scrape_engine}</dd>
            <dt className="text-slate-500">Sitemap URL</dt>
            <dd className="truncate font-mono text-xs" title={detail.sitemap_url ?? ""}>
              {detail.sitemap_url || "—"}
            </dd>
          </dl>
        </div>

        <div className="rounded-xl border border-border-subtle bg-surface-raised/50 p-5 space-y-3 text-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Schedule & activity</h3>
          <dl className="grid grid-cols-2 gap-2 text-slate-300">
            <dt className="text-slate-500">Schedule</dt>
            <dd>
              {detail.schedule_enabled ? (detail.schedule_paused ? "Paused" : "Enabled") : "Off"}
            </dd>
            <dt className="text-slate-500">Next run</dt>
            <dd>{detail.next_run_at ? <FormattedDate iso={detail.next_run_at} /> : "—"}</dd>
            <dt className="text-slate-500">Last triggered</dt>
            <dd>{detail.last_run_at ? <FormattedDate iso={detail.last_run_at} /> : "—"}</dd>
            <dt className="text-slate-500">Last job status</dt>
            <dd>
              <span className={statusPill(typeof lastStatus === "string" ? lastStatus : "pending")}>{lastStatus}</span>
            </dd>
          </dl>
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Jobs from this source</h3>
        {detail.recent_jobs.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border-subtle px-6 py-10 text-center text-sm text-slate-500">
            No jobs yet. Run this source to create one.
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border-subtle bg-surface-raised/60">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border-subtle bg-surface/80 text-xs uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Run</th>
                  <th className="px-4 py-3 font-medium">URL</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 text-right font-medium">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle/80">
                {detail.recent_jobs.map((j) => (
                  <tr key={j.id} className="hover:bg-surface-overlay/40">
                    <td className="px-4 py-3">
                      <span className={statusPill(j.status)}>{j.status}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {j.last_run_status ? <span className={statusPill(j.last_run_status)}>{j.last_run_status}</span> : "—"}
                    </td>
                    <td className="max-w-[240px] truncate px-4 py-3 text-xs text-slate-400" title={j.url ?? ""}>
                      {j.url ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {j.created_at ? <FormattedDate iso={j.created_at} /> : "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link href={`/jobs/${j.id}`} className="text-xs font-medium text-accent hover:text-accent-hover">
                        Job →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
