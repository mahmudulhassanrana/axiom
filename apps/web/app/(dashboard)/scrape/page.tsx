"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import type { ExtractedData, JobDetail } from "@/lib/jobs-types";

type QueuedScrapeResponse = {
  status: "queued";
  task_id: string;
  message: string;
};

type JobCreated = {
  id: string;
  status: string;
  celery_task_id: string | null;
  url: string | null;
};

const TERMINAL = new Set(["completed", "failed"]);
const POLL_MS = 2500;
const MAX_POLLS = 120;

function LinksPreview({ links }: { links: { href?: string; text?: string | null }[] }) {
  const slice = links.slice(0, 25);
  if (slice.length === 0) return <p className="text-xs text-slate-500">No links extracted.</p>;
  return (
    <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-xs text-slate-400">
      {slice.map((l, i) => (
        <li key={`${l.href ?? i}-${i}`} className="truncate font-mono">
          <a href={l.href} target="_blank" rel="noreferrer" className="text-indigo-300 hover:underline">
            {l.href}
          </a>
          {l.text ? <span className="ml-2 text-slate-500">({l.text})</span> : null}
        </li>
      ))}
      {links.length > 25 ? <li className="text-slate-600">…and {links.length - 25} more</li> : null}
    </ul>
  );
}

function ExtractedBlock({ row }: { row: ExtractedData }) {
  const links = Array.isArray(row.payload?.links) ? row.payload.links : [];
  const preview =
    row.text_content && row.text_content.length > 1200
      ? `${row.text_content.slice(0, 1200)}…`
      : row.text_content;
  return (
    <div className="space-y-3 border-t border-border-subtle/80 pt-4 first:border-t-0 first:pt-0">
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500">Title</div>
        <div className="mt-1 text-base font-medium text-slate-100">{row.title ?? "—"}</div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500">Text preview</div>
        <div className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-surface px-3 py-2 text-sm leading-relaxed text-slate-300">
          {preview ?? "—"}
        </div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500">Links ({links.length})</div>
        <LinksPreview links={links} />
      </div>
    </div>
  );
}

export default function ScrapePage() {
  const [url, setUrl] = useState("https://example.com");
  const [asyncExecution, setAsyncExecution] = useState(true);
  const [engine, setEngine] = useState<"html_requests" | "playwright">("html_requests");
  const [includeHtml, setIncludeHtml] = useState(false);
  const [loading, setLoading] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetail | null>(null);
  const [pollJobId, setPollJobId] = useState<string | null>(null);
  const [pollExhausted, setPollExhausted] = useState(false);
  const pollCount = useRef(0);

  const loadJob = useCallback(async (jobId: string) => {
    const j = await apiFetch<JobDetail>(`/jobs/${jobId}`);
    setJobDetail(j);
    return j;
  }, []);

  useEffect(() => {
    if (!pollJobId) return;

    let intervalId: ReturnType<typeof setInterval> | null = null;
    pollCount.current = 0;
    setPollExhausted(false);

    const tick = async () => {
      try {
        const j = await loadJob(pollJobId);
        const run = j.runs[0];
        if (run && TERMINAL.has(run.status)) {
          if (intervalId) clearInterval(intervalId);
          setPollJobId(null);
          return;
        }
        pollCount.current += 1;
        if (pollCount.current >= MAX_POLLS) {
          if (intervalId) clearInterval(intervalId);
          setPollExhausted(true);
          setPollJobId(null);
        }
      } catch {
        if (intervalId) clearInterval(intervalId);
        setPollJobId(null);
      }
    };

    void tick();
    intervalId = setInterval(() => void tick(), POLL_MS);
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [pollJobId, loadJob]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSyncResult(null);
    setJobDetail(null);
    setPollJobId(null);
    setPollExhausted(false);
    pollCount.current = 0;

    try {
      if (asyncExecution) {
        const job = await apiFetch<JobCreated>("/jobs", {
          method: "POST",
          body: JSON.stringify({ url, engine, include_html: includeHtml }),
        });
        await loadJob(job.id);
        setPollJobId(job.id);
      } else {
        const data = await apiFetch<unknown | QueuedScrapeResponse>("/scrape", {
          method: "POST",
          body: JSON.stringify({
            url,
            async: false,
            engine,
            include_html: includeHtml,
          }),
        });
        setSyncResult(JSON.stringify(data, null, 2));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const run = jobDetail?.runs[0];
  const extractedList = run?.extracted_data ?? [];
  const needResultsFallback =
    Boolean(jobDetail && run?.status === "completed" && extractedList.length === 0 && !pollExhausted);

  useEffect(() => {
    if (!needResultsFallback || !jobDetail) return;
    let cancelled = false;
    void (async () => {
      try {
        const rows = await apiFetch<ExtractedData[]>(`/jobs/${jobDetail.id}/results`);
        if (cancelled || rows.length === 0) return;
        setJobDetail((prev) => {
          if (!prev) return prev;
          const r0 = prev.runs[0];
          if (!r0) return prev;
          return {
            ...prev,
            runs: [{ ...r0, extracted_data: rows }, ...prev.runs.slice(1)],
          };
        });
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [needResultsFallback, jobDetail?.id]);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Scrape</h1>
        <p className="mt-1 text-sm text-slate-500">
          With <strong className="font-medium text-slate-400">Async</strong>, creates a{" "}
          <code className="rounded bg-surface px-1 font-mono text-[11px]">POST /jobs</code> row and shows results when
          the worker finishes. Sync calls{" "}
          <code className="rounded bg-surface px-1 font-mono text-[11px]">POST /scrape</code> inline. JWT in{" "}
          <a href="/settings" className="text-indigo-300 hover:underline">
            Settings
          </a>
          .
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow"
      >
        <label className="block">
          <span className="text-xs font-medium text-slate-400">URL</span>
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 font-mono text-sm text-slate-200 placeholder:text-slate-600 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </label>

        <div className="flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={asyncExecution}
              onChange={(e) => setAsyncExecution(e.target.checked)}
              className="rounded border-border-subtle"
            />
            Async (persisted job + worker; results below when done)
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={includeHtml}
              onChange={(e) => setIncludeHtml(e.target.checked)}
              className="rounded border-border-subtle"
            />
            Include HTML
          </label>
        </div>

        <label className="block">
          <span className="text-xs font-medium text-slate-400">Engine</span>
          <select
            value={engine}
            onChange={(e) => setEngine(e.target.value as "html_requests" | "playwright")}
            className="mt-1 w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-200 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="html_requests">html_requests</option>
            <option value="playwright">playwright</option>
          </select>
        </label>

        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {loading ? "Running…" : "Run scrape"}
        </button>
      </form>

      {error ? (
        <pre className="overflow-auto rounded-lg border border-red-900/50 bg-red-950/40 p-4 font-mono text-xs text-red-200">
          {error}
        </pre>
      ) : null}

      {jobDetail ? (
        <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-200">Job results</h2>
            <Link href={`/jobs/${jobDetail.id}`} className="text-xs text-accent hover:underline">
              Open job page →
            </Link>
          </div>
          <p className="mt-1 font-mono text-[11px] text-slate-500">{jobDetail.id}</p>
          <p className="mt-2 text-sm text-slate-400">
            Status:{" "}
            <span className="font-medium text-slate-200">{jobDetail.status}</span>
            {run ? (
              <>
                {" "}
                · Run: <span className="font-medium text-slate-200">{run.status}</span>
              </>
            ) : null}
          </p>
          {run && !TERMINAL.has(run.status) ? (
            <p className="mt-2 text-xs text-amber-200/90">Waiting for worker… (auto-refresh)</p>
          ) : null}
          {pollExhausted && run && !TERMINAL.has(run.status) ? (
            <p className="mt-2 text-xs text-amber-200/90">
              Still queued or running after several minutes. Check the worker and Redis, then open the job page.
            </p>
          ) : null}
          {run?.status === "failed" && run.error_message ? (
            <p className="mt-3 rounded-lg bg-red-950/40 px-3 py-2 text-sm text-red-200">{run.error_message}</p>
          ) : null}
          {extractedList.length > 0 ? (
            <div className="mt-6 space-y-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Extracted</h3>
              {extractedList.map((row) => (
                <ExtractedBlock key={row.id} row={row} />
              ))}
            </div>
          ) : run?.status === "completed" ? (
            <p className="mt-4 text-sm text-slate-500">No extracted rows on this run yet (check /results).</p>
          ) : null}
        </section>
      ) : null}

      {syncResult ? (
        <pre className="overflow-auto rounded-lg border border-border-subtle bg-surface p-4 font-mono text-xs text-slate-300">
          {syncResult}
        </pre>
      ) : null}
    </div>
  );
}
