export type SearchHit = {
  id: string;
  run_id: string;
  job_id: string;
  source_id: string | null;
  page_url: string;
  title: string | null;
  preview: string;
  created_at: string;
  published_date: string | null;
  country: string | null;
  city: string | null;
};

export type SearchResponse = {
  items: SearchHit[];
  total: number;
  page: number;
  limit: number;
  sort: "newest" | "oldest";
};
