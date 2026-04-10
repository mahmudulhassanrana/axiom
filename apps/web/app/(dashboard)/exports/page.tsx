import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Exports",
};

export default function ExportsPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <p className="text-sm leading-relaxed text-slate-400">
        Download extractions as JSON, CSV, Markdown, HTML, or a ZIP bundle (all formats). Use a run from the job detail
        page or call the API with a Bearer token.
      </p>
      <ul className="list-inside list-disc space-y-2 text-sm text-slate-300">
        <li>
          <code className="rounded bg-surface px-1 font-mono text-xs">GET /exports/runs/{"{run_id}"}/download?format=zip</code>
        </li>
        <li>
          <code className="rounded bg-surface px-1 font-mono text-xs">POST /exports/download</code> with body{" "}
          <code className="font-mono text-xs">format</code> + <code className="font-mono text-xs">document</code>
        </li>
      </ul>
      <Link
        href="/jobs"
        className="inline-flex rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
      >
        Go to jobs →
      </Link>
    </div>
  );
}
