import type { Metadata } from "next";
import Link from "next/link";
import { AXIOM_VERSION } from "@axiom/shared";
import { OverviewStats } from "@/components/dashboard/overview-stats";

export const metadata: Metadata = {
  title: "Overview",
};

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
        Signed-in workspace overview. Create scrape jobs from{" "}
        <Link href="/jobs" className="text-accent hover:underline">
          Jobs
        </Link>{" "}
        and track runs in real time.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <OverviewStats />
        <article className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Sources</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">—</p>
          <p className="mt-2 text-xs text-slate-500">Configure crawl sources on the Sources page.</p>
        </article>
        <article className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">App version</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{AXIOM_VERSION}</p>
          <p className="mt-2 text-xs text-slate-500">Web workspace build.</p>
        </article>
      </div>
    </div>
  );
}
