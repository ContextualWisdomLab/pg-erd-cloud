import type { Connection, Project, Snapshot, SnapshotDetail } from './types'

// Default to same-origin in production; set VITE_API_BASE_URL for dev.
const API_BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
const CSRF_STORAGE_KEY = 'csrfToken'

function csrfToken(): string {
  const existing = localStorage.getItem(CSRF_STORAGE_KEY)
  if (existing && existing.length >= 16) return existing

  const token =
    typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : Array.from(crypto.getRandomValues(new Uint8Array(24)), (byte) =>
          byte.toString(16).padStart(2, '0')
        ).join('')
  localStorage.setItem(CSRF_STORAGE_KEY, token)
  return token
}

function devHeaders(): Record<string, string> {
  const devUser = localStorage.getItem('devUser')
  return devUser ? { 'X-Dev-User': devUser } : {}
}

function jsonHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken(),
    ...devHeaders()
  }
}

export async function getMe(): Promise<{ subject: string; display_name: string | null; user_account_uuid: string }> {
  const r = await fetch(`${API_BASE}/api/me`, { credentials: 'include', headers: devHeaders() })
  if (!r.ok) throw new Error(`getMe failed: ${r.status}`)
  return r.json()
}

export async function listProjects(): Promise<Project[]> {
  const r = await fetch(`${API_BASE}/api/projects`, { credentials: 'include', headers: devHeaders() })
  if (!r.ok) throw new Error(`listProjects failed: ${r.status}`)
  return r.json()
}

export async function createProject(project_name: string): Promise<Project> {
  const r = await fetch(`${API_BASE}/api/projects`, {
    method: 'POST',
    credentials: 'include',
    headers: jsonHeaders(),
    body: JSON.stringify({ project_name })
  })
  if (!r.ok) throw new Error(`createProject failed: ${r.status}`)
  return r.json()
}

export async function listConnections(projectId: string): Promise<Connection[]> {
  const r = await fetch(`${API_BASE}/api/connections/by-project/${projectId}`, { credentials: 'include', headers: devHeaders() })
  if (!r.ok) throw new Error(`listConnections failed: ${r.status}`)
  return r.json()
}

export async function createConnection(projectId: string, conn_name: string, dsn: string): Promise<Connection> {
  const r = await fetch(`${API_BASE}/api/connections/by-project/${projectId}`, {
    method: 'POST',
    credentials: 'include',
    headers: jsonHeaders(),
    body: JSON.stringify({ conn_name, dsn })
  })
  if (!r.ok) throw new Error(`createConnection failed: ${r.status}`)
  return r.json()
}

export async function listSnapshots(projectId: string): Promise<Snapshot[]> {
  const r = await fetch(`${API_BASE}/api/snapshots/by-project/${projectId}`, { credentials: 'include', headers: devHeaders() })
  if (!r.ok) throw new Error(`listSnapshots failed: ${r.status}`)
  return r.json()
}

export async function createSnapshot(projectId: string, db_connection_uuid: string, schema_filter?: string): Promise<Snapshot> {
  const r = await fetch(`${API_BASE}/api/snapshots/by-project/${projectId}`, {
    method: 'POST',
    credentials: 'include',
    headers: jsonHeaders(),
    body: JSON.stringify({ db_connection_uuid, schema_filter: schema_filter || null })
  })
  if (!r.ok) throw new Error(`createSnapshot failed: ${r.status}`)
  return r.json()
}

export async function getSnapshot(snapshotId: string): Promise<SnapshotDetail> {
  const r = await fetch(`${API_BASE}/api/snapshots/${snapshotId}`, { credentials: 'include', headers: devHeaders() })
  if (!r.ok) throw new Error(`getSnapshot failed: ${r.status}`)
  return r.json()
}
