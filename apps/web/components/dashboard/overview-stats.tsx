"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Job } from "@/lib/jobs-types";

export function OverviewStats() {
  const [count, setCount] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const jobs = await apiFetch<Job[]>("/jobs");
      setCount(jobs.length);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load");
      setCount(null);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <article className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Jobs</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">
        {count === null ? (err ? "—" : "…") : count}
      </p>
      <p className="mt-2 text-xs text-slate-500">
        {err ? <span className="text-amber-400/90">{err}</span> : "Total jobs in your workspace."}
      </p>
    </article>
  );
}
