"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Source } from "@/lib/sources-types";
import { SourceForm } from "./source-form";

type Props = {
  sourceId: string;
};

export function SourceEditPage({ sourceId }: Props) {
  const [source, setSource] = useState<Source | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const s = await apiFetch<Source>(`/sources/${sourceId}`);
      setSource(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load source");
    } finally {
      setLoading(false);
    }
  }, [sourceId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <div className="text-sm text-slate-500">Loading…</div>;
  }

  if (error || !source) {
    return (
      <div className="space-y-4">
        <div className="text-sm text-red-300">{error ?? "Not found"}</div>
        <Link href="/sources" className="text-sm text-accent hover:text-accent-hover">
          ← Sources
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link href={`/sources/${sourceId}`} className="text-sm text-slate-500 hover:text-slate-300">
        ← Back to source
      </Link>
      <SourceForm key={source.id} mode="edit" sourceId={sourceId} initial={source} />
    </div>
  );
}
