export type ScheduleConfig = {
  type?: "cron" | "hourly" | "daily";
  cron_expression?: string | null;
  timezone?: string;
};

export type Source = {
  id: string;
  organization_id: string;
  created_by_user_id: string | null;
  name: string;
  base_url: string;
  description: string | null;
  kind: string;
  crawl_type: string;
  allow_external: boolean;
  max_pages: number;
  delay_min: number;
  delay_max: number;
  scrape_engine: string;
  include_html: boolean;
  sitemap_url: string | null;
  schedule_enabled: boolean;
  schedule_paused: boolean;
  schedule_config: ScheduleConfig | null;
  next_run_at: string | null;
  last_run_at: string | null;
  config: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type SourceJobSummary = {
  id: string;
  status: string;
  url: string | null;
  created_at: string | null;
  updated_at: string | null;
  last_run_status: string | null;
  last_run_error: string | null;
  last_run_id: string | null;
};

export type SourceDetail = Source & {
  recent_jobs: SourceJobSummary[];
};

export type SourceRunResponse = {
  job_id: string;
  run_id: string;
  celery_task_id: string | null;
  status: string;
};
