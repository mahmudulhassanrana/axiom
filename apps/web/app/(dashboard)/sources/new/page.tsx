import type { Metadata } from "next";
import Link from "next/link";
import { SourceForm } from "@/components/sources/source-form";

export const metadata: Metadata = {
  title: "New source",
};

export default function NewSourcePage() {
  return (
    <div className="space-y-6">
      <Link href="/sources" className="text-sm text-slate-500 hover:text-slate-300">
        ← All sources
      </Link>
      <SourceForm mode="create" />
    </div>
  );
}
