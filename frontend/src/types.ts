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

// Schema diff (see backend app/diff/schema_diff.py). All keys are name-based so
// the diff is stable across introspection runs (relation_oids are re-assigned).
export type DiffColumnShape = { data_type: string | null; is_not_null: boolean }
export type DiffColumnChange = { column: string; from: DiffColumnShape; to: DiffColumnShape }
export type DiffTableChange = {
  table: string
  columns: { added: string[]; removed: string[]; changed: DiffColumnChange[] }
  primary_key?: { from: string[]; to: string[] }
  comment?: { from: string | null; to: string | null }
}
export type DiffFkRef = {
  name: string | null
  child_table: string
  child_columns: string[]
  parent_table: string
  parent_columns: string[]
}
export type SchemaDiff = {
  base_table_count: number
  target_table_count: number
  tables: { added: string[]; removed: string[]; changed: DiffTableChange[] }
  foreign_keys: { added: DiffFkRef[]; removed: DiffFkRef[] }
  summary: {
    tables_added: number
    tables_removed: number
    tables_changed: number
    columns_added: number
    columns_removed: number
    columns_changed: number
    fks_added: number
    fks_removed: number
    has_changes: boolean
  }
}
export type SnapshotDiffResult = {
  base_snapshot_uuid: string
  target_snapshot_uuid: string
  status: string
  diff: SchemaDiff | null
}

// Saved diagram views (see backend app/api/diagram_views.py). layout_json is an
// opaque client payload; captureLayout/applyLayout in diagramViews.ts own its shape.
export type ViewLayout = {
  positions: Record<string, { x: number; y: number }>
}
export type DiagramView = {
  diagram_view_uuid: string
  name: string
  created_at: string
  updated_at: string
}
export type DiagramViewDetail = DiagramView & {
  layout_json: ViewLayout
}

export type ConnectionTestResult = {
  ok: boolean
  server_version: string | null
  error: string | null
}

export type TableAnnotation = {
  table_annotation_uuid: string
  schema_name: string
  relation_name: string
  body: string
  created_at: string
  updated_at: string
}

export type SnapshotDetailResponse = Omit<SnapshotDetail, 'error_message'> & {
  error_message: unknown
}

export function snapshotDetailFromResponse(response: SnapshotDetailResponse): SnapshotDetail {
  return {
    ...response,
    error_message: toPlainText(response.error_message)
  }
}
