export type Job = {
  id: string;
  organization_id: string;
  source_id: string | null;
  kind: string;
  url: string | null;
  status: string;
  celery_task_id: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type Run = {
  id: string;
  job_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  finished_at?: string | null;
  error_message: string | null;
  metrics: Record<string, unknown> | null;
};

export type MemberRecord = {
  name?: string | null;
  company?: string | null;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
  website?: string | null;
  membership_id?: string | null;
  membership_type?: string | null;
  source_url?: string | null;
  raw?: Record<string, unknown>;
};

export type ExtractedData = {
  id: string;
  run_id: string;
  source_url: string;
  final_url: string | null;
  title: string | null;
  text_content: string | null;
  payload: {
    links?: { href: string; text?: string | null }[];
    metadata?: Record<string, unknown> & { member_records?: MemberRecord[] };
    language?: string | null;
    images?: unknown[];
    files?: unknown[];
    page_url?: string;
  };
  extractor_kind: string;
  http_status: number | null;
  created_at: string;
  page_url?: string | null;
  images?: { file_url: string; file_type: string; source_url: string }[];
  files?: { file_url: string; file_type: string; source_url: string }[];
  full_text?: string | null;
  headings?: { level?: number; text?: string }[];
  internal_links?: { href: string; text?: string | null }[];
  external_links?: { href: string; text?: string | null }[];
  crawl_source?: string | null;
  content_quality_score?: number | null;
};

export type RunDetail = Run & {
  extracted_data: ExtractedData[];
};

export type AuditLogEntry = {
  id: string;
  created_at: string;
  source: string;
  url: string;
  host: string;
  engine: string | null;
  step: string;
  outcome: string;
  http_status: number | null;
  error_message: string | null;
  celery_task_id: string | null;
  extra: Record<string, unknown> | null;
};

export type JobDetail = Job & { runs: RunDetail[] };
