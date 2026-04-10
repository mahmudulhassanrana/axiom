"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Schedule = {
  id: string;
  name: string;
  cron_expression: string;
  timezone: string;
  paused: boolean;
  next_run_at: string | null;
  created_at: string;
};

export function SchedulesPageContent() {
  const [rows, setRows] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await apiFetch<Schedule[]>("/schedules");
      setRows(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="rounded-xl border border-border-subtle bg-surface-raised/50 px-6 py-12 text-center text-sm text-slate-500">
        Loading schedules…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">{error}</div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border-subtle bg-surface-raised/40 px-6 py-12 text-center text-sm text-slate-500">
        No cron schedules yet. Create one via{" "}
        <code className="rounded bg-surface px-1 font-mono text-xs text-slate-400">POST /schedules</code> or the API
        client.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border-subtle bg-surface-raised/60 shadow-glow">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border-subtle bg-surface/80 text-xs uppercase tracking-wider text-slate-500">
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Cron</th>
            <th className="px-4 py-3 font-medium">TZ</th>
            <th className="px-4 py-3 font-medium">Paused</th>
            <th className="px-4 py-3 font-medium">Next run</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle/80">
          {rows.map((s) => (
            <tr key={s.id} className="hover:bg-surface-overlay/50">
              <td className="px-4 py-3 font-medium text-slate-200">{s.name}</td>
              <td className="px-4 py-3 font-mono text-xs text-slate-400">{s.cron_expression}</td>
              <td className="px-4 py-3 text-slate-500">{s.timezone}</td>
              <td className="px-4 py-3 text-slate-400">{s.paused ? "yes" : "no"}</td>
              <td className="px-4 py-3 text-slate-500">
                {s.next_run_at ? new Date(s.next_run_at).toISOString() : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
