export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  applied_filters: Record<string, unknown>;
  snapshot_version: number;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> };
  request_id: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  data_mode: string;
  analysis_mode: string;
  ready: boolean;
  snapshot_version: number;
  dataset_updated_at?: string | null;
  ai_ready?: boolean;
  missing_ai_settings?: string[];
  data_classification?: string;
}

export interface ReferenceData {
  specialties: string[];
  states: string[];
  sources: Array<{ source_id: string; source_name: string; source_type: string }>;
  review_statuses: string[];
  review_case_types: string[];
  severities: string[];
  resolution_statuses: string[];
  record_kinds: string[];
  defaults: Record<string, unknown>;
}

export interface KpiCard {
  key: string;
  label: string;
  value: number;
  secondary_value?: number | null;
  display: string;
  tooltip: string;
  href: string;
  filters: Record<string, unknown>;
}

export interface DashboardSummary {
  dataset_updated_at?: string | null;
  last_simulated_run_at?: string | null;
  snapshot_version: number;
  applied_filters: Record<string, unknown>;
  kpis: KpiCard[];
  priority_reviews: Array<Record<string, unknown>>;
  recent_changes: Array<Record<string, unknown>>;
  source_coverage: Array<Record<string, unknown>>;
  recent_decisions: Array<Record<string, unknown>>;
}

export interface SourceBreakdownResponse {
  rows: Array<{
    source_id: string;
    source_name: string;
    segments: Array<{ status: string; count: number }>;
  }>;
  applied_filters: Record<string, unknown>;
  text_summary: string;
}

export interface DoctorListItem {
  doctor_id: string;
  preferred_name: string;
  specialty?: string | null;
  primary_affiliation?: string | null;
  affiliation_count: number;
  city?: string | null;
  state?: string | null;
  linked_record_count: number;
  pending_item_count: number;
  identity_status?: string | null;
  updated_at?: string | null;
  npi_status: string;
}

export interface DoctorSummary {
  doctor_id: string;
  preferred_name: string;
  given_name?: string | null;
  family_name?: string | null;
  specialty?: string | null;
  city?: string | null;
  state?: string | null;
  professional_email?: string | null;
  professional_phone?: string | null;
  official_npi?: string | null;
  npi_status: string;
  mock_npi_ref?: string | null;
  data_classification?: string;
  identity_status?: string | null;
  identity_review_status?: string | null;
  pending_field_changes: number;
  linked_record_count: number;
  source_count: number;
  aliases: Array<Record<string, unknown>>;
  primary_affiliation?: Record<string, unknown> | null;
  affiliations: Array<Record<string, unknown>>;
  previous_names: string[];
  pending_updates: Array<Record<string, unknown>>;
  source_coverage: Array<Record<string, unknown>>;
  credential_details?: string | null;
  updated_at?: string | null;
  version: number;
}

export interface HistoryEvent {
  event_id: string;
  doctor_id: string;
  event_type: string;
  title: string;
  description?: string | null;
  previous_value?: string | null;
  new_value?: string | null;
  document_date?: string | null;
  submitted_at?: string | null;
  submitted_to?: string | null;
  effective_date?: string | null;
  recorded_at?: string | null;
  review_status?: string | null;
  evidence_id?: string | null;
  date_label?: string | null;
  date_meaning?: string | null;
  source_type?: string | null;
  actor?: string | null;
  reason?: string | null;
  evidence_quotation?: string | null;
}

export interface SourceRecordItem {
  source_record_id: string;
  source_id: string;
  source_name?: string | null;
  record_kind: string;
  recorded_name?: string | null;
  specialty?: string | null;
  practice_name?: string | null;
  address_line?: string | null;
  city?: string | null;
  state?: string | null;
  email?: string | null;
  phone?: string | null;
  credential_reference?: string | null;
  document_id?: string | null;
  record_date?: string | null;
  submitted_at?: string | null;
  submitted_by?: string | null;
  submitted_to?: string | null;
  resolution_status?: string | null;
  link_status?: string | null;
  doctor_id?: string | null;
  evidence_ids: string[];
  normalized: Record<string, unknown>;
  linkage_explanation?: string | null;
}

export interface MatchExplanation {
  doctor_id: string;
  label?: string;
  summary: string;
  simulated_recommendation: string;
  demo_match_score?: number | null;
  decision_method: string;
  review_status?: string | null;
  ambiguities: string[];
  constraints: string[];
  side_by_side: Array<Record<string, unknown>>;
  evidence_rows: Array<Record<string, unknown>>;
}

export interface ReviewListItem {
  review_id: string;
  doctor_id?: string | null;
  doctor_name?: string | null;
  case_type: string;
  title: string;
  severity: string;
  status: string;
  source_record_id?: string | null;
  candidate_doctor_id?: string | null;
  proposed_field?: string | null;
  proposed_value?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  age_days?: number | null;
  candidates_summary?: string | null;
}

export interface ReviewDetail {
  review_id: string;
  doctor_id?: string | null;
  case_type: string;
  title: string;
  severity: string;
  status: string;
  source_record_id?: string | null;
  candidate_doctor_id?: string | null;
  proposed_field?: string | null;
  proposed_value?: string | null;
  recommendation_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  version: number;
  valid_actions: string[];
  comparison: Record<string, unknown>;
  recommendation: Record<string, unknown>;
  evidence: Array<Record<string, unknown>>;
  impact: Record<string, unknown>;
  candidates: Array<Record<string, unknown>>;
  current_state: Record<string, unknown>;
}

export interface DecisionRequest {
  decision: string;
  action: string;
  selected_doctor_id?: string | null;
  comment: string;
  expected_version: number;
  idempotency_key: string;
}

export interface DecisionResponse {
  review: ReviewDetail;
  changed_doctor_ids: string[];
  snapshot_version: number;
  audit_id: string;
}

export interface EvidenceDetail {
  evidence_id: string;
  source_record_id?: string | null;
  document_id?: string | null;
  document_version?: string | null;
  page_number?: number | null;
  block_id?: string | null;
  quoted_text?: string | null;
  source_field?: string | null;
  source_snapshot?: string | null;
  citation_label?: string | null;
  preview_kind: string;
  source_row?: Record<string, unknown> | null;
  document_title?: string | null;
  document_type?: string | null;
  associated_fields: string[];
}

export interface DocumentDetail {
  document_id: string;
  title: string;
  document_type: string;
  source_id?: string | null;
  version: string;
  document_date?: string | null;
  submitted_at?: string | null;
  submitted_by?: string | null;
  submitted_to?: string | null;
  pages: Array<{
    page_number: number;
    label?: string | null;
    blocks: Array<{ block_id: string; kind: string; text: string; highlightable?: boolean }>;
  }>;
  download_filename: string;
}

export interface SourceSummary {
  source_id: string;
  source_name: string;
  source_type: string;
  description?: string | null;
  snapshot_version?: string | null;
  updated_at?: string | null;
  row_count: number;
  linked_count: number;
  pending_count: number;
  unresolved_count: number;
  review_required_count: number;
  identifier_conflict_count: number;
  completeness?: number | null;
  latest_data_date?: string | null;
}

export interface DemoRun {
  run_id: string;
  mode: string;
  status: string;
  current_step?: string | null;
  completed_steps: number;
  total_steps: number;
  progress_percent: number;
  message?: string | null;
  started_at?: string | null;
  updated_at?: string | null;
  result_url?: string | null;
  errors: string[];
  step_labels: string[];
  result_counts?: Record<string, number> | null;
}

export interface QualitySummary {
  snapshot_version: number;
  source_completeness: Array<Record<string, unknown>>;
  missing_fields: Array<Record<string, unknown>>;
  unresolved_records: number;
  conflicting_cases: number;
  pending_review_volume: number;
  inconsistent_evidence_refs: number;
  matching_accuracy_note: string;
  drilldowns: Record<string, unknown>;
  ai_job_counts?: Record<string, number>;
}

export interface AiJob {
  job_id: string;
  status: string;
  operation?: string;
  source_record_ids?: string[];
  doctor_id?: string | null;
  review_id?: string | null;
  analysis_id?: string | null;
  status_url: string;
  requested_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  cached?: boolean;
  error?: { code?: string; message?: string } | null;
  analysis?: AiAnalysis | null;
}

export interface AiAnalysis {
  analysis_id: string;
  operation: string;
  source_record_ids: string[];
  doctor_id?: string | null;
  review_id?: string | null;
  prompt_version?: string | null;
  provider?: string | null;
  deployment?: string | null;
  requested_at?: string | null;
  completed_at?: string | null;
  response?: Record<string, unknown> | null;
  evidence_display?: Array<Record<string, unknown>>;
  token_usage?: Record<string, unknown> | null;
  error?: { code?: string; message?: string } | null;
  human_decision_status?: string | null;
  outcome?: string | null;
  label?: string | null;
  cached?: boolean;
  served_from_cache?: boolean;
}
