import type { Metadata } from "next";
import { JobsListPage } from "@/components/jobs/jobs-list-page";

export const metadata: Metadata = {
  title: "Jobs",
};

export default function JobsPage() {
  return <JobsListPage />;
}
