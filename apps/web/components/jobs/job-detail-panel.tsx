"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { FormattedDate } from "@/components/formatted-date";
import { apiDownloadBlob, apiFetch, getApiToken } from "@/lib/api";
import type { AuditLogEntry, ExtractedData, JobDetail, MemberRecord } from "@/lib/jobs-types";

function payloadMeta(r: ExtractedData): Record<string, unknown> {
  const m = r.payload?.metadata;
  return m && typeof m === "object" && !Array.isArray(m) ? (m as Record<string, unknown>) : {};
}

function memberRecordsOf(r: ExtractedData): MemberRecord[] {
  const raw = r.payload?.metadata?.member_records;
  return Array.isArray(raw) ? (raw as MemberRecord[]) : [];
}

function dedupeMembers(rows: MemberRecord[]): MemberRecord[] {
  const seen = new Set<string>();
  const out: MemberRecord[] = [];
  for (const m of rows) {
    const k = `${m.membership_id ?? ""}|${m.company ?? ""}|${m.name ?? ""}|${m.source_url ?? ""}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(m);
  }
  return out;
}

function crawlSourceOf(r: ExtractedData): string {
  if (r.crawl_source) return r.crawl_source;
  const cs = payloadMeta(r).crawl_source;
  return cs === "external" ? "external" : "internal";
}

function groupByPageUrl(rows: ExtractedData[]) {
  const m = new Map<string, ExtractedData[]>();
  for (const row of rows) {
    const key = row.page_url || row.source_url;
    const arr = m.get(key) ?? [];
    arr.push(row);
    m.set(key, arr);
  }
  return Array.from(m.entries());
}

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

function wsUrlForJob(jobId: string): string | null {
  if (typeof window === "undefined") return null;
  const token = getApiToken();
  if (!token) return null;
  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  let base: string;
  if (raw) {
    base = raw.replace(/\/$/, "").replace(/^http/i, (m) => (m.toLowerCase() === "https" ? "wss" : "ws"));
  } else {
    base = `ws://${window.location.hostname}:8000`;
  }
  return `${base}/ws/jobs/${jobId}?token=${encodeURIComponent(token)}`;
}

type Props = {
  jobId: string;
};

const TERMINAL = new Set(["completed", "failed"]);

export function JobDetailPanel({ jobId }: Props) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [results, setResults] = useState<ExtractedData[]>([]);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [openPages, setOpenPages] = useState<Record<string, boolean>>({});
  const [textExpanded, setTextExpanded] = useState<Record<string, boolean>>({});
  const [exporting, setExporting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [j, r, l] = await Promise.all([
        apiFetch<JobDetail>(`/jobs/${jobId}`),
        apiFetch<ExtractedData[]>(`/jobs/${jobId}/results`),
        apiFetch<AuditLogEntry[]>(`/jobs/${jobId}/logs`),
      ]);
      setJob(j);
      setResults(r);
      setLogs(l);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load job");
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = job?.runs[0];
  const polling = run && !TERMINAL.has(run.status);

  useEffect(() => {
    if (!polling) return;
    const t = window.setInterval(() => void load(), 8000);
    return () => window.clearInterval(t);
  }, [polling, load]);

  useEffect(() => {
    const url = wsUrlForJob(jobId);
    if (!url || !polling) return;
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(url);
      ws.onmessage = () => void load();
      ws.onerror = () => {
        /* fallback: polling */
      };
    } catch {
      /* ignore */
    }
    return () => {
      ws?.close();
    };
  }, [jobId, polling, load]);

  const internalGrouped = useMemo(
    () => groupByPageUrl(results.filter((r) => crawlSourceOf(r) !== "external")),
    [results],
  );
  const externalGrouped = useMemo(
    () => groupByPageUrl(results.filter((r) => crawlSourceOf(r) === "external")),
    [results],
  );
  const allMemberRecords = useMemo(() => {
    const acc: MemberRecord[] = [];
    for (const r of results) acc.push(...memberRecordsOf(r));
    return dedupeMembers(acc);
  }, [results]);

  async function onExport(kind: "json" | "csv" | "pdf") {
    setExporting(kind);
    try {
      await apiDownloadBlob(`/jobs/${jobId}/export/${kind}`, `job-${jobId}.${kind}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(null);
    }
  }

  function togglePage(key: string) {
    setOpenPages((o) => ({ ...o, [key]: !o[key] }));
  }

  function toggleTextExpand(key: string) {
    setTextExpanded((o) => ({ ...o, [key]: !o[key] }));
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-300">
        {error}{" "}
        <Link href="/jobs" className="text-accent hover:underline">
          Back to jobs
        </Link>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="animate-pulse rounded-xl border border-border-subtle bg-surface-raised/50 px-6 py-12 text-center text-sm text-slate-500">
        Loading job…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/jobs" className="text-xs font-medium text-slate-500 hover:text-accent">
            ← Jobs
          </Link>
          <h1 className="mt-2 text-xl font-semibold tracking-tight text-slate-100">Job</h1>
          <p className="mt-1 font-mono text-xs text-slate-500">{job.id}</p>
          <p className="mt-2 max-w-2xl break-all text-sm text-slate-400">
            {job.url ?? (typeof job.payload?.url === "string" ? job.payload.url : null) ?? "—"}
          </p>
        </div>
        <span className={statusPill(job.status)}>{job.status}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!!exporting}
          onClick={() => void onExport("json")}
          className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs text-slate-200 hover:border-accent"
        >
          {exporting === "json" ? "…" : "Download JSON"}
        </button>
        <button
          type="button"
          disabled={!!exporting}
          onClick={() => void onExport("csv")}
          className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs text-slate-200 hover:border-accent"
        >
          {exporting === "csv" ? "…" : "Download CSV"}
        </button>
        <button
          type="button"
          disabled={!!exporting}
          onClick={() => void onExport("pdf")}
          className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs text-slate-200 hover:border-accent"
        >
          {exporting === "pdf" ? "…" : "Download PDF"}
        </button>
      </div>

      <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
        <h2 className="text-sm font-semibold text-slate-200">Run status</h2>
        {run ? (
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Run ID</dt>
              <dd className="mt-0.5 font-mono text-xs text-slate-300">
                <Link href={`/runs/${run.id}`} className="text-accent hover:underline">
                  {run.id} → full run view
                </Link>
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
              <dd className="mt-0.5">
                <span className={statusPill(run.status)}>{run.status}</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Started</dt>
              <dd className="mt-0.5 text-slate-400">
                <FormattedDate iso={run.started_at} />
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Finished</dt>
              <dd className="mt-0.5 text-slate-400">
                <FormattedDate iso={run.finished_at ?? run.completed_at} />
              </dd>
            </div>
            {run.error_message ? (
              <div className="sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-red-400/80">Error</dt>
                <dd className="mt-1 rounded-lg bg-red-950/40 px-3 py-2 font-mono text-xs text-red-200">
                  {run.error_message}
                </dd>
              </div>
            ) : null}
            {run.metrics ? (
              <div className="sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-slate-500">Metrics</dt>
                <dd className="mt-1 rounded-lg bg-surface px-3 py-2 font-mono text-xs text-slate-400">
                  <pre className="whitespace-pre-wrap break-all">{JSON.stringify(run.metrics, null, 2)}</pre>
                </dd>
              </div>
            ) : null}
          </dl>
        ) : (
          <p className="mt-3 text-sm text-slate-500">No run rows yet.</p>
        )}
      </section>

      {allMemberRecords.length > 0 ? (
        <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
          <h2 className="text-sm font-semibold text-slate-200">
            Member directory — all pages ({allMemberRecords.length})
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Combined member/API rows from every extracted page in this job (deduped).
          </p>
          <div className="mt-3 max-h-[min(60vh,520px)] overflow-auto rounded border border-border-subtle">
            <table className="w-full min-w-[640px] border-collapse text-left text-xs text-slate-300">
              <thead className="sticky top-0 z-[1] bg-surface-raised/95 backdrop-blur">
                <tr className="border-b border-border-subtle text-[10px] uppercase tracking-wide text-slate-500">
                  <th className="px-2 py-2 font-medium">Company</th>
                  <th className="px-2 py-2 font-medium">Name</th>
                  <th className="px-2 py-2 font-medium">Membership</th>
                  <th className="px-2 py-2 font-medium">Type</th>
                  <th className="px-2 py-2 font-medium">Phone</th>
                  <th className="px-2 py-2 font-medium">Email</th>
                  <th className="px-2 py-2 font-medium">Web</th>
                </tr>
              </thead>
              <tbody>
                {allMemberRecords.map((m, idx) => (
                  <tr
                    key={`all-${m.membership_id ?? idx}-${idx}`}
                    className="border-b border-border-subtle/60 odd:bg-surface/40"
                  >
                    <td className="max-w-[180px] px-2 py-1.5 align-top">{m.company ?? "—"}</td>
                    <td className="max-w-[120px] px-2 py-1.5 align-top">{m.name ?? "—"}</td>
                    <td className="whitespace-nowrap px-2 py-1.5 align-top font-mono text-[10px] text-slate-400">
                      {m.membership_id ?? "—"}
                    </td>
                    <td className="px-2 py-1.5 align-top">{m.membership_type ?? "—"}</td>
                    <td className="whitespace-nowrap px-2 py-1.5 align-top font-mono text-[10px]">
                      {m.phone ?? "—"}
                    </td>
                    <td className="max-w-[140px] break-all px-2 py-1.5 align-top">{m.email ?? "—"}</td>
                    <td className="max-w-[120px] break-all px-2 py-1.5 align-top text-accent/90">
                      {m.website ? (
                        <a href={m.website} target="_blank" rel="noreferrer" className="hover:underline">
                          {m.website}
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {internalGrouped.length > 0 ? (
        <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
          <h2 className="text-sm font-semibold text-slate-200">
            Primary pages ({internalGrouped.length})
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Same-domain and seed URLs. Full text, headings, and link lists; asset URLs are references only.
          </p>
          <ul className="mt-4 space-y-2">
            {internalGrouped.map(([pageUrl, rows]) => {
              const open = openPages[`i:${pageUrl}`] ?? false;
              const row = rows[0];
              const fullText = row.full_text ?? row.text_content ?? "—";
              const expanded = textExpanded[`i:${pageUrl}`] ?? false;
              const longBody = fullText.length > 1400;
              const headings =
                row.headings ??
                (Array.isArray(payloadMeta(row).headings) ? (payloadMeta(row).headings as ExtractedData["headings"]) : []);
              const q =
                row.content_quality_score ??
                (typeof payloadMeta(row).content_quality_score === "number"
                  ? (payloadMeta(row).content_quality_score as number)
                  : null);
              const members = memberRecordsOf(row);
              return (
                <li key={`i:${pageUrl}`} className="rounded-lg border border-border-subtle bg-surface/60">
                  <button
                    type="button"
                    onClick={() => togglePage(`i:${pageUrl}`)}
                    className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-slate-200 hover:bg-surface-overlay/40"
                  >
                    <span className="break-all font-mono text-xs text-accent">{pageUrl}</span>
                    <span className="shrink-0 text-xs text-slate-500">{open ? "▼" : "▶"}</span>
                  </button>
                  {open ? (
                    <div className="space-y-3 border-t border-border-subtle px-3 py-3 text-sm">
                      <div>
                        <div className="text-xs uppercase text-slate-500">Title</div>
                        <div className="text-slate-100">{row.title ?? "—"}</div>
                      </div>
                      {q != null ? (
                        <div className="text-xs text-slate-500">Content quality: {q.toFixed(3)}</div>
                      ) : null}
                      {headings && headings.length > 0 ? (
                        <div>
                          <div className="text-xs uppercase text-slate-500">Headings</div>
                          <ul className="mt-1 max-h-40 overflow-auto text-xs text-slate-300">
                            {headings.map((h, i) => (
                              <li key={i}>
                                H{h.level ?? "?"}: {h.text ?? ""}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {members.length > 0 ? (
                        <div>
                          <div className="text-xs uppercase text-slate-500">
                            Member records ({members.length})
                          </div>
                          <div className="mt-2 max-h-[min(60vh,520px)] overflow-auto rounded border border-border-subtle">
                            <table className="w-full min-w-[640px] border-collapse text-left text-xs text-slate-300">
                              <thead className="sticky top-0 z-[1] bg-surface-raised/95 backdrop-blur">
                                <tr className="border-b border-border-subtle text-[10px] uppercase tracking-wide text-slate-500">
                                  <th className="px-2 py-2 font-medium">Company</th>
                                  <th className="px-2 py-2 font-medium">Name</th>
                                  <th className="px-2 py-2 font-medium">Membership</th>
                                  <th className="px-2 py-2 font-medium">Type</th>
                                  <th className="px-2 py-2 font-medium">Phone</th>
                                  <th className="px-2 py-2 font-medium">Email</th>
                                  <th className="px-2 py-2 font-medium">Web</th>
                                </tr>
                              </thead>
                              <tbody>
                                {members.map((m, idx) => (
                                  <tr
                                    key={`${m.membership_id ?? idx}-${idx}`}
                                    className="border-b border-border-subtle/60 odd:bg-surface/40"
                                  >
                                    <td className="max-w-[180px] px-2 py-1.5 align-top">{m.company ?? "—"}</td>
                                    <td className="max-w-[120px] px-2 py-1.5 align-top">{m.name ?? "—"}</td>
                                    <td className="whitespace-nowrap px-2 py-1.5 align-top font-mono text-[10px] text-slate-400">
                                      {m.membership_id ?? "—"}
                                    </td>
                                    <td className="px-2 py-1.5 align-top">{m.membership_type ?? "—"}</td>
                                    <td className="whitespace-nowrap px-2 py-1.5 align-top font-mono text-[10px]">
                                      {m.phone ?? "—"}
                                    </td>
                                    <td className="max-w-[140px] break-all px-2 py-1.5 align-top">{m.email ?? "—"}</td>
                                    <td className="max-w-[120px] break-all px-2 py-1.5 align-top text-accent/90">
                                      {m.website ? (
                                        <a href={m.website} target="_blank" rel="noreferrer" className="hover:underline">
                                          {m.website}
                                        </a>
                                      ) : (
                                        "—"
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      ) : null}
                      <div>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-xs uppercase text-slate-500">Full text</div>
                          {longBody ? (
                            <button
                              type="button"
                              onClick={() => toggleTextExpand(`i:${pageUrl}`)}
                              className="text-xs text-accent hover:underline"
                            >
                              {expanded ? "Show less" : "Show more"}
                            </button>
                          ) : null}
                        </div>
                        <div
                          className={`overflow-auto whitespace-pre-wrap rounded bg-surface px-2 py-2 text-slate-300 ${
                            expanded || !longBody ? "max-h-[min(70vh,2400px)]" : "max-h-48"
                          }`}
                        >
                          {fullText}
                        </div>
                      </div>
                      <div className="text-xs text-slate-500">
                        Links: {Array.isArray(row.payload?.links) ? row.payload.links.length : 0} · Internal:{" "}
                        {row.internal_links?.length ??
                          (Array.isArray(payloadMeta(row).internal_links)
                            ? (payloadMeta(row).internal_links as unknown[]).length
                            : 0)}{" "}
                        · External:{" "}
                        {row.external_links?.length ??
                          (Array.isArray(payloadMeta(row).external_links)
                            ? (payloadMeta(row).external_links as unknown[]).length
                            : 0)}{" "}
                        · Images: {row.images?.length ?? row.payload?.images?.length ?? 0} · Files:{" "}
                        {row.files?.length ?? row.payload?.files?.length ?? 0}
                      </div>
                      {(row.images?.length ?? 0) > 0 ? (
                        <div>
                          <div className="text-xs uppercase text-slate-500">Image URLs</div>
                          <ul className="mt-1 max-h-32 overflow-auto font-mono text-[11px] text-slate-400">
                            {(row.images ?? (row.payload?.images as ExtractedData["images"]) ?? []).map((im, i) => (
                              <li key={i} className="break-all">
                                {(im as { file_url?: string }).file_url ?? JSON.stringify(im)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {(row.files?.length ?? 0) > 0 ? (
                        <div>
                          <div className="text-xs uppercase text-slate-500">File links</div>
                          <ul className="mt-1 max-h-32 overflow-auto font-mono text-[11px] text-slate-400">
                            {(row.files ?? (row.payload?.files as ExtractedData["files"]) ?? []).map((f, i) => (
                              <li key={i} className="break-all">
                                {(f as { file_url?: string; file_type?: string }).file_url ?? JSON.stringify(f)}
                                {(f as { file_type?: string }).file_type
                                  ? ` (${(f as { file_type?: string }).file_type})`
                                  : ""}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {externalGrouped.length > 0 ? (
        <section className="rounded-xl border border-amber-900/30 bg-amber-950/10 p-5 shadow-glow">
          <h2 className="text-sm font-semibold text-amber-200/90">
            External pages ({externalGrouped.length})
          </h2>
          <p className="mt-1 text-xs text-amber-200/60">Off-domain URLs scraped when external crawling was enabled.</p>
          <ul className="mt-4 space-y-2">
            {externalGrouped.map(([pageUrl, rows]) => {
              const open = openPages[`e:${pageUrl}`] ?? false;
              const row = rows[0];
              const fullText = row.full_text ?? row.text_content ?? "—";
              const expanded = textExpanded[`e:${pageUrl}`] ?? false;
              const longBody = fullText.length > 1400;
              return (
                <li key={`e:${pageUrl}`} className="rounded-lg border border-border-subtle bg-surface/60">
                  <button
                    type="button"
                    onClick={() => togglePage(`e:${pageUrl}`)}
                    className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-slate-200 hover:bg-surface-overlay/40"
                  >
                    <span className="break-all font-mono text-xs text-amber-300/90">{pageUrl}</span>
                    <span className="shrink-0 text-xs text-slate-500">{open ? "▼" : "▶"}</span>
                  </button>
                  {open ? (
                    <div className="space-y-3 border-t border-border-subtle px-3 py-3 text-sm">
                      <div>
                        <div className="text-xs uppercase text-slate-500">Title</div>
                        <div className="text-slate-100">{row.title ?? "—"}</div>
                      </div>
                      <div>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-xs uppercase text-slate-500">Full text</div>
                          {longBody ? (
                            <button
                              type="button"
                              onClick={() => toggleTextExpand(`e:${pageUrl}`)}
                              className="text-xs text-accent hover:underline"
                            >
                              {expanded ? "Show less" : "Show more"}
                            </button>
                          ) : null}
                        </div>
                        <div
                          className={`overflow-auto whitespace-pre-wrap rounded bg-surface px-2 py-2 text-slate-300 ${
                            expanded || !longBody ? "max-h-[min(70vh,2400px)]" : "max-h-48"
                          }`}
                        >
                          {fullText}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-200">Audit log</h2>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-md border border-border-subtle px-2 py-1 text-xs text-slate-400 hover:border-accent hover:text-slate-200"
          >
            Refresh
          </button>
        </div>
        <p className="mt-1 text-xs text-slate-500">Compliance and fetch steps recorded for this job (newest first).</p>
        {logs.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No log entries yet.</p>
        ) : (
          <ul className="mt-4 max-h-[420px] space-y-2 overflow-auto rounded-lg border border-border-subtle bg-surface p-3 font-mono text-[11px] leading-relaxed text-slate-400">
            {logs.map((row) => (
              <li
                key={row.id}
                className="border-b border-border-subtle/60 pb-2 last:border-0 last:pb-0"
              >
                <span className="text-slate-600">{new Date(row.created_at).toISOString()}</span>{" "}
                <span className="text-indigo-300">[{row.source}]</span>{" "}
                <span className="text-slate-300">{row.step}</span>{" "}
                <span
                  className={
                    row.outcome === "success" || row.outcome === "ok"
                      ? "text-emerald-400"
                      : row.outcome === "denied" || row.outcome === "error"
                        ? "text-red-400"
                        : "text-amber-300"
                  }
                >
                  {row.outcome}
                </span>
                {row.http_status != null ? <span className="text-slate-500"> http={row.http_status}</span> : null}
                <div className="mt-0.5 text-slate-500">{row.url}</div>
                {row.error_message ? <div className="mt-1 text-red-300/90">{row.error_message}</div> : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
