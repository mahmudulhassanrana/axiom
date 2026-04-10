"use client";

import { usePathname } from "next/navigation";
import { AuthGuard } from "@/components/auth/auth-guard";
import { DashboardShell } from "./dashboard-shell";

export function DashboardLayoutClient({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  let headerTitle = "Overview";
  if (segments[0] === "scrape") {
    headerTitle = "Scrape";
  } else if (segments[0] === "jobs" && segments[1]) {
    headerTitle = "Job detail";
  } else if (segments[0] === "jobs") {
    headerTitle = "Jobs";
  } else if (segments[0] === "runs" && segments[1]) {
    headerTitle = "Run results";
  } else if (segments[0] === "sources") {
    headerTitle = "Sources";
  } else if (segments[0] === "schedules") {
    headerTitle = "Schedules";
  } else if (segments[0] === "exports") {
    headerTitle = "Exports";
  } else if (segments[0] === "settings") {
    headerTitle = "Settings";
  }

  return (
    <AuthGuard>
      <DashboardShell headerTitle={headerTitle} headerDescription="Compliant ingestion and scraping operations">
        {children}
      </DashboardShell>
    </AuthGuard>
  );
}
