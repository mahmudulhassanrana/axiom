"use client";

import { useState } from "react";
import { toast } from "sonner";

type Props = {
  onCreated: () => void;
};

export function JobCreateForm({ onCreated }: Props) {
  const [url, setUrl] = useState("https://example.com");
  const [engine, setEngine] = useState<"html_requests" | "playwright">("html_requests");
  const [includeHtml, setIncludeHtml] = useState(false);
  const [crawlMaxPages, setCrawlMaxPages] = useState(5);
  const [crawlDelaySeconds, setCrawlDelaySeconds] = useState(1.5);
  const [crawlJitterSeconds, setCrawlJitterSeconds] = useState(0.5);
  const [crawlAllowExternal, setCrawlAllowExternal] = useState(false);
  const [crawlMaxExternalPages, setCrawlMaxExternalPages] = useState(25);
  const [crawlMaxExternalPerHost, setCrawlMaxExternalPerHost] = useState(5);
  const [preFetchJitterMax, setPreFetchJitterMax] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { apiFetch } = await import("@/lib/api");
      await apiFetch("/jobs", {
        method: "POST",
        body: JSON.stringify({
          url,
          engine,
          include_html: includeHtml,
          crawl_max_pages: crawlMaxPages,
          crawl_delay_seconds: crawlDelaySeconds,
          crawl_jitter_seconds: crawlJitterSeconds,
          crawl_allow_external: crawlAllowExternal,
          crawl_max_external_pages: crawlMaxExternalPages,
          crawl_max_external_per_host: crawlMaxExternalPerHost,
          pre_fetch_jitter_max_seconds: preFetchJitterMax,
        }),
      });
      setUrl("https://");
      toast.success("Job created");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow backdrop-blur-sm"
    >
      <h2 className="text-sm font-semibold tracking-tight text-slate-200">New scrape job</h2>
      <p className="mt-1 text-xs text-slate-500">
        Max pages is your total budget (list + member detail pages + pagination). Use at least 3–5 for member
        directories. Optional external links stay within page/host caps and compliance (robots, rate limits).
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">URL</span>
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            placeholder="https://example.com/page"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <label className="block min-w-[8rem] flex-1">
            <span className="mb-1 block text-xs font-medium text-slate-400">Engine</span>
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value as "html_requests" | "playwright")}
              className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            >
              <option value="html_requests">HTTP + parse</option>
              <option value="playwright">Playwright</option>
            </select>
          </label>
          <label className="flex cursor-pointer items-center gap-2 self-end pb-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={includeHtml}
              onChange={(e) => setIncludeHtml(e.target.checked)}
              className="rounded border-border-subtle bg-surface text-accent focus:ring-accent"
            />
            Include HTML
          </label>
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">Max pages (1–50)</span>
          <input
            type="number"
            min={1}
            max={50}
            value={crawlMaxPages}
            onChange={(e) => setCrawlMaxPages(Math.min(50, Math.max(1, Number(e.target.value) || 1)))}
            className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">Delay (s)</span>
          <input
            type="number"
            min={0.5}
            max={10}
            step={0.1}
            value={crawlDelaySeconds}
            onChange={(e) => setCrawlDelaySeconds(Number(e.target.value) || 1.5)}
            className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">Jitter (s)</span>
          <input
            type="number"
            min={0}
            max={5}
            step={0.1}
            value={crawlJitterSeconds}
            onChange={(e) => setCrawlJitterSeconds(Number(e.target.value) || 0)}
            className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
          <input
            type="checkbox"
            checked={crawlAllowExternal}
            onChange={(e) => setCrawlAllowExternal(e.target.checked)}
            className="rounded border-border-subtle bg-surface text-accent focus:ring-accent"
          />
          Allow external links (capped)
        </label>
        <label className="block min-w-[7rem]">
          <span className="mb-1 block text-xs font-medium text-slate-400">Ext. URL budget</span>
          <input
            type="number"
            min={0}
            max={50}
            value={crawlMaxExternalPages}
            onChange={(e) => setCrawlMaxExternalPages(Math.min(50, Math.max(0, Number(e.target.value) || 0)))}
            disabled={!crawlAllowExternal}
            className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 disabled:opacity-40"
          />
        </label>
        <label className="block min-w-[7rem]">
          <span className="mb-1 block text-xs font-medium text-slate-400">Per external host</span>
          <input
            type="number"
            min={1}
            max={20}
            value={crawlMaxExternalPerHost}
            onChange={(e) => setCrawlMaxExternalPerHost(Math.min(20, Math.max(1, Number(e.target.value) || 1)))}
            disabled={!crawlAllowExternal}
            className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 disabled:opacity-40"
          />
        </label>
        <label className="block min-w-[7rem]">
          <span className="mb-1 block text-xs font-medium text-slate-400">Pre-fetch jitter max (s)</span>
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={preFetchJitterMax}
            onChange={(e) => setPreFetchJitterMax(Math.min(2, Math.max(0, Number(e.target.value) || 0)))}
            className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100"
          />
        </label>
      </div>
      {error ? (
        <p className="mt-3 rounded-lg bg-red-950/50 px-3 py-2 text-xs text-red-300 ring-1 ring-red-900/80">{error}</p>
      ) : null}
      <div className="mt-4 flex justify-end">
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-950/50 transition hover:bg-accent-hover disabled:opacity-50"
        >
          {loading ? "Creating…" : "Create job"}
        </button>
      </div>
    </form>
  );
}
