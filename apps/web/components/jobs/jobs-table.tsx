"use client";

import Link from "next/link";
import { FormattedDate } from "@/components/formatted-date";
import type { Job } from "@/lib/jobs-types";

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
  jobs: Job[];
};

export function JobsTable({ jobs }: Props) {
  if (jobs.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border-subtle bg-surface-raised/40 px-6 py-12 text-center text-sm text-slate-500">
        No jobs yet. Create one above or enqueue from the API.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border-subtle bg-surface-raised/60 shadow-glow">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border-subtle bg-surface/80 text-xs uppercase tracking-wider text-slate-500">
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">URL</th>
            <th className="px-4 py-3 font-medium">Kind</th>
            <th className="px-4 py-3 font-medium">Created</th>
            <th className="px-4 py-3 font-medium">Task</th>
            <th className="px-4 py-3 font-medium text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle/80">
          {jobs.map((job) => (
            <tr key={job.id} className="transition hover:bg-surface-overlay/50">
              <td className="px-4 py-3">
                <span className={statusPill(job.status)}>{job.status}</span>
              </td>
              <td className="max-w-[min(280px,40vw)] truncate px-4 py-3 text-xs text-slate-400" title={job.url ?? ""}>
                {job.url ?? (typeof job.payload?.url === "string" ? job.payload.url : "—")}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-slate-400">{job.kind}</td>
              <td className="px-4 py-3 text-slate-400">
                <FormattedDate iso={job.created_at} />
              </td>
              <td className="max-w-[200px] truncate px-4 py-3 font-mono text-xs text-slate-500" title={job.celery_task_id ?? ""}>
                {job.celery_task_id ?? "—"}
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  href={`/jobs/${job.id}`}
                  className="text-xs font-medium text-accent hover:text-accent-hover"
                >
                  View →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
