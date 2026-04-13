import type { Metadata } from "next";
import { SourceEditPage } from "@/components/sources/source-edit-page";

type Props = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: `Edit source ${id.slice(0, 8)}…` };
}

export default async function EditSourceRoute({ params }: Props) {
  const { id } = await params;
  return <SourceEditPage sourceId={id} />;
}
