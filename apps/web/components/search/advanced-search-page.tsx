"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FormattedDate } from "@/components/formatted-date";
import { apiFetch, ApiError } from "@/lib/api";
import type { SearchResponse } from "@/lib/search-types";

const COUNTRY_HINTS = [
  "Bangladesh",
  "United States",
  "United Kingdom",
  "India",
  "Canada",
  "Germany",
  "France",
  "Australia",
  "Japan",
  "Brazil",
];

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function HighlightPreview({ text, keyword }: { text: string; keyword: string }) {
  const kw = keyword.trim();
  if (!kw || !text) {
    return <span className="text-slate-400">{text || "—"}</span>;
  }
  const parts = text.split(new RegExp(`(${escapeRegExp(kw)})`, "gi"));
  return (
    <span className="text-slate-400">
      {parts.map((part, i) =>
        part.toLowerCase() === kw.toLowerCase() ? (
          <mark key={i} className="rounded bg-amber-500/30 px-0.5 text-amber-100">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </span>
  );
}

function HighlightTitle({ title, keyword }: { title: string | null; keyword: string }) {
  if (!title) return <span className="text-slate-500">—</span>;
  return <HighlightPreview text={title} keyword={keyword} />;
}

export function AdvancedSearchPage() {
  const [keyword, setKeyword] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [jobId, setJobId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const limit = 20;

  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchedKeyword, setSearchedKeyword] = useState("");

  const buildQuery = useCallback(
    (p: number) => {
      const q = new URLSearchParams();
      if (keyword.trim()) q.set("keyword", keyword.trim());
      if (country.trim()) q.set("country", country.trim());
      if (city.trim()) q.set("city", city.trim());
      if (dateFrom) {
        const t = Date.parse(`${dateFrom}T00:00:00.000Z`);
        if (!Number.isNaN(t)) q.set("date_from", new Date(t).toISOString());
      }
      if (dateTo) {
        const t = Date.parse(`${dateTo}T00:00:00.000Z`);
        if (!Number.isNaN(t)) {
          const end = new Date(t);
          end.setUTCHours(23, 59, 59, 999);
          q.set("date_to", end.toISOString());
        }
      }
      const jt = jobId.trim();
      if (jt && UUID_RE.test(jt)) q.set("job_id", jt);
      const st = sourceId.trim();
      if (st && UUID_RE.test(st)) q.set("source_id", st);
      q.set("page", String(p));
      q.set("limit", String(limit));
      q.set("sort", sort);
      return q.toString();
    },
    [keyword, country, city, dateFrom, dateTo, jobId, sourceId, sort],
  );

  const runSearch = useCallback(
    async (p: number) => {
      setError(null);
      setLoading(true);
      setSearchedKeyword(keyword.trim());
      try {
        const qs = buildQuery(p);
        const res = await apiFetch<SearchResponse>(`/search?${qs}`);
        setData(res);
      } catch (e) {
        setData(null);
        setError(e instanceof ApiError ? e.message : "Search failed");
      } finally {
        setLoading(false);
      }
    },
    [buildQuery, keyword],
  );

  useEffect(() => {
    void runSearch(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial recent results; form state is empty
  }, []);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void runSearch(1);
  };

  const totalPages = useMemo(() => {
    if (!data) return 0;
    return Math.max(1, Math.ceil(data.total / data.limit));
  }, [data]);

  const field =
    "w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent";

  return (
    <div className="space-y-8">
      <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
        Search extracted pages by keyword, location, and ingested date. Leave filters blank to see the latest results;
        from/to dates apply to ingested time. Published date is still shown on each row when available.
      </p>

      <form onSubmit={onSubmit} className="rounded-xl border border-border-subtle bg-surface-raised/50 p-6 space-y-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-1 lg:col-span-2">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Keyword</label>
            <input
              className={field}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="Search title or extracted text…"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Country</label>
            <input className={field} value={country} onChange={(e) => setCountry(e.target.value)} list="country-hints" />
            <datalist id="country-hints">
              {COUNTRY_HINTS.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-500">City</label>
            <input className={field} value={city} onChange={(e) => setCity(e.target.value)} placeholder="City" />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-500">From date</label>
            <input className={field} type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-500">To date</label>
            <input className={field} type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Sort</label>
            <select className={field} value={sort} onChange={(e) => setSort(e.target.value as "newest" | "oldest")}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Job ID (optional)</label>
            <input className={field} value={jobId} onChange={(e) => setJobId(e.target.value)} placeholder="UUID" />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Source ID (optional)</label>
            <input className={field} value={sourceId} onChange={(e) => setSourceId(e.target.value)} placeholder="UUID" />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-white shadow-glow hover:bg-accent-hover disabled:opacity-50"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}

      {loading && !data ? (
        <div className="rounded-xl border border-border-subtle bg-surface-raised/40 px-6 py-12 text-center text-sm text-slate-500">
          Loading…
        </div>
      ) : null}

      {loading && data ? (
        <p className="text-xs text-slate-500" aria-live="polite">
          Updating results…
        </p>
      ) : null}

      {!loading && data && data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border-subtle px-6 py-12 text-center text-sm text-slate-500">
          No results found. Try different filters or clear optional fields.
        </div>
      ) : null}

      {data && data.items.length > 0 ? (
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            {data.total} result{data.total === 1 ? "" : "s"} · page {data.page} of {totalPages}
          </p>
          <ul className="space-y-3">
            {data.items.map((hit) => (
              <li
                key={hit.id}
                className="rounded-xl border border-border-subtle bg-surface-raised/50 p-4 transition hover:bg-surface-overlay/40"
              >
                <Link href={`/jobs/${hit.job_id}`} className="block space-y-2">
                  <div className="text-sm font-semibold text-slate-100">
                    <HighlightTitle title={hit.title} keyword={searchedKeyword} />
                  </div>
                  <p className="text-xs leading-relaxed">
                    <HighlightPreview text={hit.preview} keyword={searchedKeyword} />
                  </p>
                  <p className="font-mono text-[11px] text-indigo-300/90 break-all">{hit.page_url}</p>
                  <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
                    <span>
                      Date:{" "}
                      {hit.published_date ? (
                        <FormattedDate iso={hit.published_date} />
                      ) : (
                        <FormattedDate iso={hit.created_at} />
                      )}
                      {hit.published_date ? " (published)" : " (ingested)"}
                    </span>
                    {(hit.country || hit.city) && (
                      <span>
                        {hit.city ? `${hit.city}` : ""}
                        {hit.city && hit.country ? ", " : ""}
                        {hit.country ? hit.country : ""}
                      </span>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2 pt-2">
            <button
              type="button"
              disabled={(data.page ?? 1) <= 1 || loading}
              onClick={() => void runSearch((data.page ?? 1) - 1)}
              className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs text-slate-300 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={(data.page ?? 1) >= totalPages || loading}
              onClick={() => void runSearch((data.page ?? 1) + 1)}
              className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs text-slate-300 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
