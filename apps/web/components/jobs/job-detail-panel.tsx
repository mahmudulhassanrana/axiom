"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { FormattedDate } from "@/components/formatted-date";
import { apiFetch } from "@/lib/api";
import type { AuditLogEntry, JobDetail } from "@/lib/jobs-types";

function statusPill(status: string) {
  const base = "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide";
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
  jobId: string;
};

const TERMINAL = new Set(["completed", "failed"]);

export function JobDetailPanel({ jobId }: Props) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [j, l] = await Promise.all([
        apiFetch<JobDetail>(`/jobs/${jobId}`),
        apiFetch<AuditLogEntry[]>(`/jobs/${jobId}/logs`),
      ]);
      setJob(j);
      setLogs(l);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load job");
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = job?.runs[0];
  const polling = run && !TERMINAL.has(run.status);

  useEffect(() => {
    if (!polling) return;
    const t = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(t);
  }, [polling, load]);

  if (error) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-300">
        {error}{" "}
        <Link href="/jobs" className="text-accent hover:underline">
          Back to jobs
        </Link>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="animate-pulse rounded-xl border border-border-subtle bg-surface-raised/50 px-6 py-12 text-center text-sm text-slate-500">
        Loading job…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/jobs" className="text-xs font-medium text-slate-500 hover:text-accent">
            ← Jobs
          </Link>
          <h1 className="mt-2 text-xl font-semibold tracking-tight text-slate-100">Job</h1>
          <p className="mt-1 font-mono text-xs text-slate-500">{job.id}</p>
          <p className="mt-2 max-w-2xl break-all text-sm text-slate-400">
            {job.url ?? (typeof job.payload?.url === "string" ? job.payload.url : null) ?? "—"}
          </p>
        </div>
        <span className={statusPill(job.status)}>{job.status}</span>
      </div>

      <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
        <h2 className="text-sm font-semibold text-slate-200">Run status</h2>
        {run ? (
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Run ID</dt>
              <dd className="mt-0.5 font-mono text-xs text-slate-300">
                <Link href={`/runs/${run.id}`} className="text-accent hover:underline">
                  {run.id} → full run view
                </Link>
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
              <dd className="mt-0.5">
                <span className={statusPill(run.status)}>{run.status}</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Started</dt>
              <dd className="mt-0.5 text-slate-400">
                <FormattedDate iso={run.started_at} />
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Finished</dt>
              <dd className="mt-0.5 text-slate-400">
                <FormattedDate iso={run.finished_at ?? run.completed_at} />
              </dd>
            </div>
            {run.error_message ? (
              <div className="sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-red-400/80">Error</dt>
                <dd className="mt-1 rounded-lg bg-red-950/40 px-3 py-2 font-mono text-xs text-red-200">
                  {run.error_message}
                </dd>
              </div>
            ) : null}
            {run.metrics ? (
              <div className="sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-slate-500">Metrics</dt>
                <dd className="mt-1 rounded-lg bg-surface px-3 py-2 font-mono text-xs text-slate-400">
                  <pre className="whitespace-pre-wrap break-all">{JSON.stringify(run.metrics, null, 2)}</pre>
                </dd>
              </div>
            ) : null}
          </dl>
        ) : (
          <p className="mt-3 text-sm text-slate-500">No run rows yet.</p>
        )}
      </section>

      {run && "extracted_data" in run && run.extracted_data.length > 0 ? (
        <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
          <h2 className="text-sm font-semibold text-slate-200">Extracted</h2>
          {run.extracted_data.map((row) => (
            <div key={row.id} className="mt-4 space-y-3 border-t border-border-subtle/80 pt-4 first:mt-0 first:border-t-0 first:pt-0">
              <div>
                <div className="text-xs uppercase tracking-wide text-slate-500">Title</div>
                <div className="mt-1 text-base font-medium text-slate-100">{row.title ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-slate-500">Text preview</div>
                <div className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-surface px-3 py-2 text-sm leading-relaxed text-slate-300">
                  {row.text_content
                    ? row.text_content.length > 1200
                      ? `${row.text_content.slice(0, 1200)}…`
                      : row.text_content
                    : "—"}
                </div>
              </div>
              <p className="text-xs text-slate-500">
                Links: {Array.isArray(row.payload?.links) ? row.payload.links.length : 0}
              </p>
            </div>
          ))}
        </section>
      ) : null}

      <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-200">Audit log</h2>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-md border border-border-subtle px-2 py-1 text-xs text-slate-400 hover:border-accent hover:text-slate-200"
          >
            Refresh
          </button>
        </div>
        <p className="mt-1 text-xs text-slate-500">Compliance and fetch steps recorded for this job (newest first).</p>
        {logs.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No log entries yet.</p>
        ) : (
          <ul className="mt-4 max-h-[420px] space-y-2 overflow-auto rounded-lg border border-border-subtle bg-surface p-3 font-mono text-[11px] leading-relaxed text-slate-400">
            {logs.map((row) => (
              <li
                key={row.id}
                className="border-b border-border-subtle/60 pb-2 last:border-0 last:pb-0"
              >
                <span className="text-slate-600">
                  {new Date(row.created_at).toISOString()}
                </span>{" "}
                <span className="text-indigo-300">[{row.source}]</span>{" "}
                <span className="text-slate-300">{row.step}</span>{" "}
                <span
                  className={
                    row.outcome === "success" || row.outcome === "ok"
                      ? "text-emerald-400"
                      : row.outcome === "denied" || row.outcome === "error"
                        ? "text-red-400"
                        : "text-amber-300"
                  }
                >
                  {row.outcome}
                </span>
                {row.http_status != null ? (
                  <span className="text-slate-500"> http={row.http_status}</span>
                ) : null}
                <div className="mt-0.5 text-slate-500">{row.url}</div>
                {row.error_message ? (
                  <div className="mt-1 text-red-300/90">{row.error_message}</div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
