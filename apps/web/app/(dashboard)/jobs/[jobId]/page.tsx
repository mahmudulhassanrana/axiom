import type { Metadata } from "next";
import { JobDetailPanel } from "@/components/jobs/job-detail-panel";

type Props = {
  params: Promise<{ jobId: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { jobId } = await params;
  return {
    title: `Job ${jobId.slice(0, 8)}…`,
  };
}

export default async function JobDetailPage({ params }: Props) {
  const { jobId } = await params;
  return <JobDetailPanel jobId={jobId} />;
}
