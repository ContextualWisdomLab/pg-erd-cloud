export type Project = {
  project_space_uuid: string
  project_name: string
}

export type Connection = {
  db_connection_uuid: string
  conn_name: string
}

export type SnapshotJson = {
  relations?: Array<{ relation_oid: number; relation_kind: string; schema_name: string; relation_name: string; relation_comment?: string | null }>
  columns?: Array<{ relation_oid: number; column_name: string; data_type: string; is_not_null: boolean; column_comment?: string | null; example_value?: string | number | boolean | null }>
  constraints?: Array<{
    constraint_oid: number
    constraint_name: string
    constraint_type: string
    relation_oid?: number
    foreign_relation_oid?: number
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
  error_message: string | null
  snapshot_json: SnapshotJson | null
}
