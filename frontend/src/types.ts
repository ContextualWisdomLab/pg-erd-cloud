export type Project = {
  project_space_uuid: string
  project_name: string
}

export type Connection = {
  db_connection_uuid: string
  conn_name: string
}

export type ShareLink = {
  share_link_uuid: string
  permission_kind: string
  url_path: string
  url: string
}

declare const plainTextBrand: unique symbol

export type PlainText = string & { readonly [plainTextBrand]: true }

const HTML_TEXT_ENTITIES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
}

export function toPlainText(value: unknown): PlainText | null {
  if (typeof value !== 'string' || value.length === 0) return null

  return value
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, ' ')
    .replace(/[&<>"']/g, (char) => HTML_TEXT_ENTITIES[char])
    .trim() as PlainText
}

export type SnapshotJson = {
  relations?: Array<{ relation_oid: number; relation_kind: string; schema_name: string; relation_name: string; relation_comment?: string | null }>
  columns?: Array<{ relation_oid: number; column_name: string; data_type: string; is_not_null: boolean; column_comment?: string | null; example_value?: string | number | boolean | null }>
  constraints?: Array<{
    constraint_oid: number
    constraint_name: string
    constraint_type: string
    schema_name: string
    relation_oid: number
    relation_name: string
    foreign_relation_oid?: number | null
    foreign_schema_name?: string | null
    foreign_relation_name?: string | null
    constrained_attnums?: number[] | null
    referenced_attnums?: number[] | null
    fk_on_update?: string | null
    fk_on_delete?: string | null
    fk_match_type?: string | null
    constraint_def?: string | null
    check_expr?: string | null
  }>
  pk_columns?: Array<{ relation_oid: number; column_name: string }>
  fk_edges?: Array<{
    fk_constraint_oid: number
    fk_constraint_name: string
    child_relation_oid: number
    parent_relation_oid: number
    child_column_name: string
    parent_column_name: string
    column_ordinal: number
  }>
  indexes?: Array<{
    relation_oid?: number
    table_oid?: number
    index_name: string
    access_method?: string
    access_method_extension?: string | null
    operator_class_extensions?: string[]
    is_unique?: boolean
    is_primary?: boolean
    index_def?: string
  }>
}

export type Snapshot = {
  schema_snapshot_uuid: string
  status: string
  schema_filter: string | null
}

export type SnapshotDetail = {
  schema_snapshot_uuid: string
  status: string
  schema_filter: string | null
  error_message: PlainText | null
  snapshot_json: SnapshotJson | null
}

export type SnapshotDetailResponse = Omit<SnapshotDetail, 'error_message'> & {
  error_message: unknown
}

export type MigrationRunState =
  | 'queued'
  | 'sandbox_running'
  | 'live_preflight_running'
  | 'passed'
  | 'drifted'
  | 'failed'
  | 'applying'
  | 'reconciling'
  | 'verifying'
  | 'verified'
  | 'drifted_no_apply'
  | 'not_applied'
  | 'verification_failed'
  | 'failed_rolled_back'
  | 'applied_with_drift'
  | 'outcome_unknown'

export type MigrationPlan = {
  migration_plan_uuid: string
  project_space_uuid: string
  schema_model_revision_uuid: string
  db_connection_uuid: string
  base_schema_snapshot_uuid: string
  plan_digest: string
  base_digest: string
  target_digest: string
  compiler_version: string
  snapshot_contract_version: number
  postgresql_major: number
  created_by_user_uuid: string
  created_at: string
  can_dry_run: boolean
  requires_destructive_confirmation: boolean
  statements: ReadonlyArray<Readonly<Record<string, unknown>>>
  proposed_statements: ReadonlyArray<Readonly<Record<string, unknown>>>
  blockers: ReadonlyArray<Readonly<Record<string, unknown>>>
  risk_summary: Readonly<{ safe: number; warning: number; destructive: number }>
  expires_at: string
}

export type MigrationRunAction = {
  migration_run_uuid: string
  state: MigrationRunState
  state_version: number
  cancellation_requested: boolean
  reused: boolean
}

export type MigrationRunEvent = {
  sequence_number: number
  event_type: string
  state_before: string | null
  state_after: string
  evidence: Readonly<Record<string, unknown>>
  previous_event_digest: string | null
  event_digest: string
  actor_user_uuid: string | null
  created_at: string
}

export type MigrationRun = {
  migration_run_uuid: string
  project_space_uuid: string
  migration_plan_uuid: string
  run_kind: 'dry_run' | 'apply'
  state: MigrationRunState
  state_version: number
  plan_digest: string
  requested_by_user_uuid: string
  cancellation_requested: boolean
  observed_base_digest: string | null
  evidence: Readonly<Record<string, unknown>>
  error_code: string | null
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
  events: ReadonlyArray<MigrationRunEvent>
}

export type MigrationApplyIntent = {
  plan_digest: string
  passed_dry_run_uuid: string
  target_connection_name: string
  destructive_acknowledged: boolean
}

export function snapshotDetailFromResponse(response: SnapshotDetailResponse): SnapshotDetail {
  return {
    ...response,
    error_message: toPlainText(response.error_message)
  }
}
