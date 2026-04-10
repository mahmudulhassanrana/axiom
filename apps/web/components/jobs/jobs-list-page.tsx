"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Job } from "@/lib/jobs-types";
import { JobCreateForm } from "./job-create-form";
import { JobsTable } from "./jobs-table";

export function JobsListPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const data = await apiFetch<Job[]>("/jobs");
      setJobs(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-8">
      <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
        Create scrape jobs backed by Celery. Each job runs compliance checks, then the worker fetches the URL and
        updates run status. Open a job to see live status and audit logs.
      </p>

      <JobCreateForm onCreated={() => void refresh()} />

      {error ? (
        <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          <strong className="font-medium">API:</strong> {error}
          <span className="mt-1 block text-xs text-amber-200/80">
            Add a Bearer token under Settings if requests return 401.
          </span>
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-border-subtle bg-surface-raised/50 px-6 py-10 text-center text-sm text-slate-500">
          Loading jobs…
        </div>
      ) : (
        <JobsTable jobs={jobs} />
      )}
    </div>
  );
}
