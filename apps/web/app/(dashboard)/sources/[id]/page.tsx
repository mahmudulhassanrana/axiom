import type { Metadata } from "next";
import { SourceDetailPage } from "@/components/sources/source-detail-page";

type Props = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: `Source ${id.slice(0, 8)}…` };
}

export default async function SourceDetailRoute({ params }: Props) {
  const { id } = await params;
  return <SourceDetailPage sourceId={id} />;
}
