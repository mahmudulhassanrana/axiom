import type { Metadata } from "next";
import { SchedulesPageContent } from "@/components/schedules/schedules-page-content";

export const metadata: Metadata = {
  title: "Schedules",
};

export default function SchedulesPage() {
  return <SchedulesPageContent />;
}
