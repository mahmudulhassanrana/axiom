"use client";

import { useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";

type QueuedResponse = {
  status: "queued";
  task_id: string;
  message: string;
};

export default function ScrapePage() {
  const [url, setUrl] = useState("https://example.com");
  const [asyncExecution, setAsyncExecution] = useState(true);
  const [engine, setEngine] = useState<"html_requests" | "playwright">("html_requests");
  const [includeHtml, setIncludeHtml] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await apiFetch<unknown | QueuedResponse>("/scrape", {
        method: "POST",
        body: JSON.stringify({
          url,
          async: asyncExecution,
          engine,
          include_html: includeHtml,
        }),
      });
      setResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Scrape</h1>
        <p className="mt-1 text-sm text-slate-500">
          Calls <code className="rounded bg-surface px-1 py-0.5 font-mono text-[11px]">POST /scrape</code>. Save a JWT under{" "}
          <a href="/settings" className="text-indigo-300 hover:underline">
            Settings
          </a>{" "}
          first.
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
            Async (Celery queue; returns 202 + task_id)
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

      {result ? (
        <pre className="overflow-auto rounded-lg border border-border-subtle bg-surface p-4 font-mono text-xs text-slate-300">
          {result}
        </pre>
      ) : null}
    </div>
  );
}
