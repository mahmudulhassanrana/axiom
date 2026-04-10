"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { FormattedDate } from "@/components/formatted-date";
import { apiFetch } from "@/lib/api";
import type { RunDetail } from "@/lib/jobs-types";

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

type Props = { runId: string };

export function RunDetailView({ runId }: Props) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await apiFetch<RunDetail>(`/runs/${runId}`);
      setRun(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load run");
    }
  }, [runId]);

  useEffect(() => {
    void load();
  }, [load]);

  const polling = run && !["completed", "failed"].includes(run.status);
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

  if (!run) {
    return (
      <div className="animate-pulse rounded-xl border border-border-subtle bg-surface-raised/50 px-6 py-12 text-center text-sm text-slate-500">
        Loading run…
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
          <h1 className="mt-2 text-xl font-semibold tracking-tight text-slate-100">Run</h1>
          <p className="mt-1 font-mono text-xs text-slate-500">{run.id}</p>
          <p className="mt-1 font-mono text-xs text-slate-600">Job {run.job_id}</p>
        </div>
        <span className={statusPill(run.status)}>{run.status}</span>
      </div>

      <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
        <h2 className="text-sm font-semibold text-slate-200">Timing</h2>
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Started</dt>
            <dd className="text-slate-400">
              <FormattedDate iso={run.started_at} />
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Finished</dt>
            <dd className="text-slate-400">
              <FormattedDate iso={run.finished_at ?? run.completed_at} />
            </dd>
          </div>
        </dl>
        {run.error_message ? (
          <p className="mt-4 rounded-lg bg-red-950/40 px-3 py-2 font-mono text-xs text-red-200">{run.error_message}</p>
        ) : null}
      </section>

      {run.extracted_data.length > 0 ? (
        <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
          <h2 className="text-sm font-semibold text-slate-200">Extracted content</h2>
          {run.extracted_data.map((row) => {
            const meta = row.payload?.metadata;
            const metaTags =
              meta &&
              typeof meta === "object" &&
              meta !== null &&
              "meta_tags" in meta &&
              typeof (meta as { meta_tags?: unknown }).meta_tags === "object"
                ? ((meta as { meta_tags: Record<string, string> }).meta_tags as Record<string, string>)
                : null;
            return (
            <div key={row.id} className="mt-4 space-y-4 border-t border-border-subtle/80 pt-4 first:mt-0 first:border-t-0 first:pt-0">
              <div>
                <div className="text-xs uppercase tracking-wide text-slate-500">Title</div>
                <div className="mt-1 text-lg font-medium text-slate-100">{row.title ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-slate-500">Text</div>
                <div className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-surface px-3 py-2 text-sm leading-relaxed text-slate-300">
                  {row.text_content ?? "—"}
                </div>
              </div>
              {Array.isArray(row.payload?.links) && row.payload.links.length > 0 ? (
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500">Links ({row.payload.links.length})</div>
                  <ul className="mt-2 max-h-48 space-y-1 overflow-auto rounded-lg border border-border-subtle bg-surface p-3 font-mono text-[11px] text-indigo-300">
                    {row.payload.links.slice(0, 200).map((link, i) => (
                      <li key={`${link.href}-${i}`}>
                        <a href={link.href} target="_blank" rel="noreferrer" className="hover:underline">
                          {link.href}
                        </a>
                        {link.text ? <span className="text-slate-500"> — {link.text}</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {metaTags && Object.keys(metaTags).length > 0 ? (
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500">Meta tags</div>
                  <dl className="mt-2 grid gap-1 text-xs text-slate-400">
                    {Object.entries(metaTags)
                      .slice(0, 40)
                      .map(([k, v]) => (
                        <div key={k} className="flex gap-2">
                          <dt className="shrink-0 font-mono text-slate-500">{k}</dt>
                          <dd className="break-all">{v}</dd>
                        </div>
                      ))}
                  </dl>
                </div>
              ) : null}
            </div>
            );
          })}
        </section>
      ) : (
        <div className="rounded-xl border border-dashed border-border-subtle bg-surface-raised/40 px-6 py-10 text-center text-sm text-slate-500">
          No extracted rows yet. The worker may still be running.
        </div>
      )}
    </div>
  );
}
