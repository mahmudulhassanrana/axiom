"use client";

import Link from "next/link";
import { FormattedDate } from "@/components/formatted-date";
import type { Source } from "@/lib/sources-types";

type Props = {
  sources: Source[];
};

export function SourcesTable({ sources }: Props) {
  if (sources.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border-subtle bg-surface-raised/40 px-6 py-12 text-center text-sm text-slate-500">
        No sources yet. Create a reusable target to run scrapes with shared crawl settings.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border-subtle bg-surface-raised/60 shadow-glow">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border-subtle bg-surface/80 text-xs uppercase tracking-wider text-slate-500">
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Base URL</th>
            <th className="px-4 py-3 font-medium">Crawl</th>
            <th className="px-4 py-3 font-medium">Schedule</th>
            <th className="px-4 py-3 font-medium">Updated</th>
            <th className="px-4 py-3 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle/80">
          {sources.map((s) => (
            <tr key={s.id} className="transition hover:bg-surface-overlay/50">
              <td className="px-4 py-3 font-medium text-slate-200">{s.name}</td>
              <td className="max-w-[min(280px,40vw)] truncate px-4 py-3 text-xs text-slate-400" title={s.base_url}>
                {s.base_url}
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">
                {s.crawl_type}
                <span className="block text-[10px] text-slate-500">
                  max {s.max_pages} · {s.delay_min}–{s.delay_max}s
                  {s.allow_external ? " · external" : ""}
                </span>
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">
                {s.schedule_enabled ? (s.schedule_paused ? "paused" : "on") : "off"}
              </td>
              <td className="px-4 py-3 text-slate-400">
                <FormattedDate iso={s.updated_at} />
              </td>
              <td className="px-4 py-3 text-right">
                <Link href={`/sources/${s.id}`} className="text-xs font-medium text-accent hover:text-accent-hover">
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
