import type { Metadata } from "next";
import { RunDetailView } from "@/components/runs/run-detail-view";

type Props = {
  params: Promise<{ runId: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { runId } = await params;
  return {
    title: `Run ${runId.slice(0, 8)}…`,
  };
}

export default async function RunPage({ params }: Props) {
  const { runId } = await params;
  return <RunDetailView runId={runId} />;
}
