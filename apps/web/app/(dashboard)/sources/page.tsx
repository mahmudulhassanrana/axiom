import type { Metadata } from "next";
import { SourcesListPage } from "@/components/sources/sources-list-page";

export const metadata: Metadata = {
  title: "Sources",
};

export default function SourcesPage() {
  return <SourcesListPage />;
}
