"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { ScheduleConfig, Source } from "@/lib/sources-types";

export type SourceFormValues = {
  name: string;
  base_url: string;
  description: string;
  crawl_type: "single_page" | "multi_page" | "sitemap";
  allow_external: boolean;
  max_pages: number;
  delay_min: number;
  delay_max: number;
  scrape_engine: "html_requests" | "playwright";
  include_html: boolean;
  sitemap_url: string;
  schedule_enabled: boolean;
  schedule_paused: boolean;
  schedule_type: "cron" | "hourly" | "daily";
  cron_expression: string;
  is_active: boolean;
};

const defaultValues = (): SourceFormValues => ({
  name: "",
  base_url: "https://",
  description: "",
  crawl_type: "single_page",
  allow_external: false,
  max_pages: 1,
  delay_min: 1.5,
  delay_max: 2.5,
  scrape_engine: "html_requests",
  include_html: false,
  sitemap_url: "",
  schedule_enabled: false,
  schedule_paused: false,
  schedule_type: "daily",
  cron_expression: "0 0 * * *",
  is_active: true,
});

export function valuesFromSource(s: Source): SourceFormValues {
  const cfg = s.schedule_config;
  const st = cfg?.type ?? "daily";
  const schedule_type: SourceFormValues["schedule_type"] =
    st === "hourly" ? "hourly" : st === "daily" ? "daily" : "cron";
  return {
    name: s.name,
    base_url: s.base_url,
    description: s.description ?? "",
    crawl_type: s.crawl_type as SourceFormValues["crawl_type"],
    allow_external: s.allow_external,
    max_pages: s.max_pages,
    delay_min: s.delay_min,
    delay_max: s.delay_max,
    scrape_engine: s.scrape_engine as SourceFormValues["scrape_engine"],
    include_html: s.include_html,
    sitemap_url: s.sitemap_url ?? "",
    schedule_enabled: s.schedule_enabled,
    schedule_paused: s.schedule_paused,
    schedule_type,
    cron_expression: typeof cfg?.cron_expression === "string" ? cfg.cron_expression : "0 * * * *",
    is_active: s.is_active,
  };
}

function buildScheduleConfig(v: SourceFormValues): ScheduleConfig | null {
  if (!v.schedule_enabled) return null;
  if (v.schedule_type === "hourly") return { type: "hourly", timezone: "UTC" };
  if (v.schedule_type === "daily") return { type: "daily", timezone: "UTC" };
  return { type: "cron", cron_expression: v.cron_expression.trim(), timezone: "UTC" };
}

type Props = {
  mode: "create" | "edit";
  sourceId?: string;
  initial?: Source;
};

export function SourceForm({ mode, sourceId, initial }: Props) {
  const router = useRouter();
  const [v, setV] = useState<SourceFormValues>(() => (initial ? valuesFromSource(initial) : defaultValues()));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function validate(): string | null {
    if (!v.name.trim()) return "Name is required.";
    try {
      void new URL(v.base_url.trim());
    } catch {
      return "Enter a valid base URL.";
    }
    if (v.max_pages < 1 || v.max_pages > 50) return "Max pages must be between 1 and 50.";
    if (v.delay_min < 0.5 || v.delay_max > 30 || v.delay_max < v.delay_min) {
      return "Delays must be 0.5–30s and delay max ≥ min.";
    }
    if (v.schedule_enabled && v.schedule_type === "cron" && v.cron_expression.trim().length < 9) {
      return "Enter a valid cron expression.";
    }
    return null;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const msg = validate();
    if (msg) {
      setError(msg);
      return;
    }
    setError(null);
    setBusy(true);
    const schedule_config = buildScheduleConfig(v);
    const body: Record<string, unknown> = {
      name: v.name.trim(),
      base_url: v.base_url.trim(),
      description: v.description.trim() || null,
      crawl_type: v.crawl_type,
      allow_external: v.allow_external,
      max_pages: v.max_pages,
      delay_min: v.delay_min,
      delay_max: v.delay_max,
      scrape_engine: v.scrape_engine,
      include_html: v.include_html,
      sitemap_url: v.sitemap_url.trim() || null,
      schedule_enabled: v.schedule_enabled,
      schedule_paused: v.schedule_paused,
      schedule_config: v.schedule_enabled ? schedule_config : null,
      is_active: v.is_active,
    };
    try {
      if (mode === "create") {
        const created = await apiFetch<Source>("/sources", { method: "POST", body: JSON.stringify(body) });
        router.push(`/sources/${created.id}`);
      } else if (sourceId) {
        await apiFetch<Source>(`/sources/${sourceId}`, { method: "PUT", body: JSON.stringify(body) });
        router.push(`/sources/${sourceId}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  const field =
    "block w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent";

  return (
    <form onSubmit={(e) => void onSubmit(e)} className="max-w-2xl space-y-6">
      {error ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}

      <div className="space-y-2">
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Name</label>
        <input className={field} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} required />
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Base URL</label>
        <input className={field} value={v.base_url} onChange={(e) => setV({ ...v, base_url: e.target.value })} required />
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Description</label>
        <textarea className={field} rows={3} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Crawl type</label>
          <select
            className={field}
            value={v.crawl_type}
            onChange={(e) => setV({ ...v, crawl_type: e.target.value as SourceFormValues["crawl_type"] })}
          >
            <option value="single_page">Single page</option>
            <option value="multi_page">Multi-page (same site)</option>
            <option value="sitemap">Sitemap</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Max pages</label>
          <input
            type="number"
            min={1}
            max={50}
            className={field}
            value={v.max_pages}
            onChange={(e) => setV({ ...v, max_pages: Number(e.target.value) })}
          />
        </div>
      </div>

      {v.crawl_type === "sitemap" ? (
        <div className="space-y-2">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Sitemap URL (optional)</label>
          <input
            className={field}
            placeholder="Defaults to /sitemap.xml under base URL"
            value={v.sitemap_url}
            onChange={(e) => setV({ ...v, sitemap_url: e.target.value })}
          />
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Delay min (s)</label>
          <input
            type="number"
            step="0.1"
            min={0.5}
            max={30}
            className={field}
            value={v.delay_min}
            onChange={(e) => setV({ ...v, delay_min: Number(e.target.value) })}
          />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Delay max (s)</label>
          <input
            type="number"
            step="0.1"
            min={0.5}
            max={30}
            className={field}
            value={v.delay_max}
            onChange={(e) => setV({ ...v, delay_max: Number(e.target.value) })}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={v.allow_external}
            onChange={(e) => setV({ ...v, allow_external: e.target.checked })}
            className="rounded border-border-subtle"
          />
          Allow external links
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={v.include_html}
            onChange={(e) => setV({ ...v, include_html: e.target.checked })}
            className="rounded border-border-subtle"
          />
          Include HTML
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={v.is_active}
            onChange={(e) => setV({ ...v, is_active: e.target.checked })}
            className="rounded border-border-subtle"
          />
          Active
        </label>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Engine</label>
        <select
          className={field}
          value={v.scrape_engine}
          onChange={(e) => setV({ ...v, scrape_engine: e.target.value as SourceFormValues["scrape_engine"] })}
        >
          <option value="html_requests">HTML (requests)</option>
          <option value="playwright">Playwright</option>
        </select>
      </div>

      <div className="rounded-xl border border-border-subtle bg-surface/60 p-4 space-y-4">
        <label className="flex items-center gap-2 text-sm font-medium text-slate-200">
          <input
            type="checkbox"
            checked={v.schedule_enabled}
            onChange={(e) => setV({ ...v, schedule_enabled: e.target.checked })}
            className="rounded border-border-subtle"
          />
          Enable schedule (Celery Beat)
        </label>
        {v.schedule_enabled ? (
          <>
            <label className="flex items-center gap-2 text-sm text-slate-400">
              <input
                type="checkbox"
                checked={v.schedule_paused}
                onChange={(e) => setV({ ...v, schedule_paused: e.target.checked })}
                className="rounded border-border-subtle"
              />
              Paused
            </label>
            <div className="space-y-2">
              <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Preset</label>
              <select
                className={field}
                value={v.schedule_type}
                onChange={(e) => setV({ ...v, schedule_type: e.target.value as SourceFormValues["schedule_type"] })}
              >
                <option value="hourly">Hourly</option>
                <option value="daily">Daily (UTC midnight)</option>
                <option value="cron">Custom cron</option>
              </select>
            </div>
            {v.schedule_type === "cron" ? (
              <div className="space-y-2">
                <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Cron (5-field)</label>
                <input
                  className={field}
                  value={v.cron_expression}
                  onChange={(e) => setV({ ...v, cron_expression: e.target.value })}
                  placeholder="0 * * * *"
                />
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white shadow-glow transition hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? "Saving…" : mode === "create" ? "Create source" : "Save changes"}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="rounded-lg border border-border-subtle px-4 py-2 text-sm text-slate-300 hover:bg-surface-overlay"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
