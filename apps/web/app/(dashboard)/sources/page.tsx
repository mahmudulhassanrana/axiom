import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sources",
};

export default function SourcesPage() {
  return (
    <div className="space-y-4">
      <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
        Crawl sources and base URLs will be managed here. API wiring is not connected yet.
      </p>
      <div className="rounded-xl border border-dashed border-border-subtle bg-surface-raised/40 px-6 py-12 text-center text-sm text-slate-500">
        No sources configured.
      </div>
    </div>
  );
}
