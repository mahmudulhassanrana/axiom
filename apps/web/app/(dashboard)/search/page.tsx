import type { Metadata } from "next";
import { AdvancedSearchPage } from "@/components/search/advanced-search-page";

export const metadata: Metadata = {
  title: "Advanced Search",
};

export default function SearchRoutePage() {
  return <AdvancedSearchPage />;
}
