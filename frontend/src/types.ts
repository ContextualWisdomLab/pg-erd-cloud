export type Project = {
  project_space_uuid: string
  project_name: string
}

export type Connection = {
  db_connection_uuid: string
  conn_name: string
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
  snapshot_json: any | null
}
