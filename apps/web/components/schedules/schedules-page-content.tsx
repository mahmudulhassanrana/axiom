"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";

type Schedule = {
  id: string;
  name: string | null;
  cron_expression: string;
  timezone: string;
  paused: boolean;
  next_run_at: string | null;
  created_at: string;
};

type CronPreset = "hourly" | "daily" | "custom";

const PRESET_CRON: Record<Exclude<CronPreset, "custom">, string> = {
  hourly: "0 * * * *",
  daily: "0 0 * * *",
};

export function SchedulesPageContent() {
  const [rows, setRows] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [cronPreset, setCronPreset] = useState<CronPreset>("hourly");
  const [cronCustom, setCronCustom] = useState("0 * * * *");
  const [url, setUrl] = useState("https://example.com");
  const [engine, setEngine] = useState<"html_requests" | "playwright">("html_requests");
  const [includeHtml, setIncludeHtml] = useState(false);
  const [crawlMaxPages, setCrawlMaxPages] = useState(1);
  const [crawlDelaySeconds, setCrawlDelaySeconds] = useState(1.5);
  const [crawlJitterSeconds, setCrawlJitterSeconds] = useState(0.5);
  const [crawlAllowExternal, setCrawlAllowExternal] = useState(false);
  const [crawlMaxExternalPages, setCrawlMaxExternalPages] = useState(25);
  const [crawlMaxExternalPerHost, setCrawlMaxExternalPerHost] = useState(5);
  const [preFetchJitterMax, setPreFetchJitterMax] = useState(0);
  const [togglingId, setTogglingId] = useState<string | null>(null);

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

  const cronExpression = cronPreset === "custom" ? cronCustom : PRESET_CRON[cronPreset];

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setCreating(true);
    try {
      await apiFetch<Schedule>("/schedules", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim() || null,
          cron_expression: cronExpression.trim(),
          timezone: "UTC",
          max_retries: 5,
          payload: {
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
          },
        }),
      });
      toast.success("Schedule created");
      setName("");
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create schedule");
    } finally {
      setCreating(false);
    }
  }

  async function setPaused(id: string, paused: boolean) {
    setTogglingId(id);
    try {
      await apiFetch(`/schedules/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ paused }),
      });
      toast.success(paused ? "Schedule paused" : "Schedule resumed");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
    } finally {
      setTogglingId(null);
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-border-subtle bg-surface-raised/50 px-6 py-12 text-center text-sm text-slate-500">
        Loading schedules…
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <form
        onSubmit={onCreate}
        className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow backdrop-blur-sm"
      >
        <h2 className="text-sm font-semibold tracking-tight text-slate-200">New recurring schedule</h2>
        <p className="mt-1 text-xs text-slate-500">
          Cron is evaluated in UTC. Each tick enqueues a scrape job with the same options as a manual job.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-xs font-medium text-slate-400">Name (optional)</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              placeholder="Nightly product crawl"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-400">Interval</span>
            <select
              value={cronPreset}
              onChange={(e) => setCronPreset(e.target.value as CronPreset)}
              className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            >
              <option value="hourly">Hourly (0 * * * *)</option>
              <option value="daily">Daily at midnight UTC (0 0 * * *)</option>
              <option value="custom">Custom cron</option>
            </select>
          </label>
          {cronPreset === "custom" ? (
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-400">Cron (5 fields, UTC)</span>
              <input
                type="text"
                required
                value={cronCustom}
                onChange={(e) => setCronCustom(e.target.value)}
                className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 font-mono text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                placeholder="0 */6 * * *"
              />
            </label>
          ) : null}
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-xs font-medium text-slate-400">URL</span>
            <input
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </label>
          <label className="block">
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
          <label className="flex cursor-pointer items-center gap-2 sm:col-span-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={crawlAllowExternal}
              onChange={(e) => setCrawlAllowExternal(e.target.checked)}
              className="rounded border-border-subtle bg-surface text-accent focus:ring-accent"
            />
            Allow external links (capped)
          </label>
          <label className="block">
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
          <label className="block">
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
          <label className="block">
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
        {formError ? (
          <p className="mt-3 rounded-lg bg-red-950/50 px-3 py-2 text-xs text-red-300 ring-1 ring-red-900/80">{formError}</p>
        ) : null}
        <div className="mt-4 flex justify-end">
          <button
            type="submit"
            disabled={creating}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-950/50 transition hover:bg-accent-hover disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create schedule"}
          </button>
        </div>
      </form>

      {error ? (
        <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">{error}</div>
      ) : null}

      {rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border-subtle bg-surface-raised/40 px-6 py-12 text-center text-sm text-slate-500">
          No cron schedules yet. Create one with the form above.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border-subtle bg-surface-raised/60 shadow-glow">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle bg-surface/80 text-xs uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Cron</th>
                <th className="px-4 py-3 font-medium">TZ</th>
                <th className="px-4 py-3 font-medium">Paused</th>
                <th className="px-4 py-3 font-medium">Next run</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle/80">
              {rows.map((s) => (
                <tr key={s.id} className="hover:bg-surface-overlay/50">
                  <td className="px-4 py-3 font-medium text-slate-200">{s.name ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">{s.cron_expression}</td>
                  <td className="px-4 py-3 text-slate-500">{s.timezone}</td>
                  <td className="px-4 py-3 text-slate-400">{s.paused ? "yes" : "no"}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {s.next_run_at ? new Date(s.next_run_at).toISOString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {s.paused ? (
                      <button
                        type="button"
                        disabled={togglingId === s.id}
                        onClick={() => void setPaused(s.id, false)}
                        className="rounded-md border border-border-subtle px-2 py-1 text-xs text-slate-200 hover:border-accent disabled:opacity-50"
                      >
                        {togglingId === s.id ? "…" : "Resume"}
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={togglingId === s.id}
                        onClick={() => void setPaused(s.id, true)}
                        className="rounded-md border border-border-subtle px-2 py-1 text-xs text-slate-200 hover:border-accent disabled:opacity-50"
                      >
                        {togglingId === s.id ? "…" : "Pause"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
