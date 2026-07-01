import { snapshotDetailFromResponse } from './types'
import type { Connection, Project, Snapshot, SnapshotDetail, SnapshotDetailResponse } from './types'

// Default to same-origin in production; set VITE_API_BASE_URL for dev.
const API_BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

type CsrfTokenResponse = {
  csrf_token: string
}

function isLocalDevelopmentHost(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'
}

function requireSecureCredentialTransport(): void {
  const targetUrl = new URL(API_BASE || window.location.origin, window.location.origin)
  if (targetUrl.protocol !== 'https:' && !isLocalDevelopmentHost(targetUrl.hostname)) {
    throw new Error('createConnection requires HTTPS for credential transport')
  }
}

async function csrfToken(): Promise<string> {
  const r = await fetch(`${API_BASE}/api/csrf-token`, {
    credentials: 'include',
    headers: devHeaders()
  })
  if (!r.ok) throw new Error(`csrfToken failed: ${r.status}`)

  const payload = (await r.json()) as Partial<CsrfTokenResponse>
  if (typeof payload.csrf_token !== 'string' || !payload.csrf_token) {
    throw new Error('csrfToken failed: invalid token response')
  }
  return payload.csrf_token
}

function devHeaders(): Record<string, string> {
  const devUser = localStorage.getItem('devUser')
  return devUser ? { 'X-Dev-User': devUser } : {}
}

async function jsonHeaders(): Promise<Record<string, string>> {
  return {
    'Content-Type': 'application/json',
    'X-CSRF-Token': await csrfToken(),
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
    headers: await jsonHeaders(),
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
  requireSecureCredentialTransport()
  const r = await fetch(`${API_BASE}/api/connections/by-project/${projectId}`, {
    method: 'POST',
    credentials: 'include',
    headers: await jsonHeaders(),
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
    headers: await jsonHeaders(),
    body: JSON.stringify({ db_connection_uuid, schema_filter: schema_filter || null })
  })
  if (!r.ok) throw new Error(`createSnapshot failed: ${r.status}`)
  return r.json()
}

export async function getSnapshot(snapshotId: string): Promise<SnapshotDetail> {
  const r = await fetch(`${API_BASE}/api/snapshots/${snapshotId}`, { credentials: 'include', headers: devHeaders() })
  if (!r.ok) throw new Error(`getSnapshot failed: ${r.status}`)
  const response = (await r.json()) as SnapshotDetailResponse
  return snapshotDetailFromResponse(response)
}
