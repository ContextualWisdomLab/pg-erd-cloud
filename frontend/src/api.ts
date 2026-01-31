import type { Connection, Project, Snapshot, SnapshotDetail } from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function listProjects(): Promise<Project[]> {
  const r = await fetch(`${API_BASE}/api/projects`)
  if (!r.ok) throw new Error(`listProjects failed: ${r.status}`)
  return r.json()
}

export async function createProject(project_name: string): Promise<Project> {
  const r = await fetch(`${API_BASE}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_name })
  })
  if (!r.ok) throw new Error(`createProject failed: ${r.status}`)
  return r.json()
}

export async function listConnections(projectId: string): Promise<Connection[]> {
  const r = await fetch(`${API_BASE}/api/connections/by-project/${projectId}`)
  if (!r.ok) throw new Error(`listConnections failed: ${r.status}`)
  return r.json()
}

export async function createConnection(projectId: string, conn_name: string, dsn: string): Promise<Connection> {
  const r = await fetch(`${API_BASE}/api/connections/by-project/${projectId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conn_name, dsn })
  })
  if (!r.ok) throw new Error(`createConnection failed: ${r.status}`)
  return r.json()
}

export async function listSnapshots(projectId: string): Promise<Snapshot[]> {
  const r = await fetch(`${API_BASE}/api/snapshots/by-project/${projectId}`)
  if (!r.ok) throw new Error(`listSnapshots failed: ${r.status}`)
  return r.json()
}

export async function createSnapshot(projectId: string, db_connection_uuid: string, schema_filter?: string): Promise<Snapshot> {
  const r = await fetch(`${API_BASE}/api/snapshots/by-project/${projectId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ db_connection_uuid, schema_filter: schema_filter || null })
  })
  if (!r.ok) throw new Error(`createSnapshot failed: ${r.status}`)
  return r.json()
}

export async function getSnapshot(snapshotId: string): Promise<SnapshotDetail> {
  const r = await fetch(`${API_BASE}/api/snapshots/${snapshotId}`)
  if (!r.ok) throw new Error(`getSnapshot failed: ${r.status}`)
  return r.json()
}
