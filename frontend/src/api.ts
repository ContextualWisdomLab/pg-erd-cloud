import { snapshotDetailFromResponse } from './types'
import type {
  Connection,
  DiagramView,
  DiagramViewDetail,
  DiagramViewLayout,
  Project,
  ShareLink,
  Snapshot,
  SnapshotDetail,
  SnapshotDetailResponse,
  SnapshotJson,
} from './types'

// Default to same-origin in production; set VITE_API_BASE_URL for dev.
const API_BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

let demoProjects: Project[] = [
  { project_space_uuid: 'demo-shopping', project_name: '쇼핑몰 시스템' },
  { project_space_uuid: 'demo-hr', project_name: '회사 인사관리' },
  { project_space_uuid: 'demo-parking', project_name: '전자상거래 DB' }
]

const demoConnectionsByProject: Record<string, Connection[]> = {
  'demo-shopping': [{ db_connection_uuid: 'demo-shopping-db', conn_name: 'production-readonly' }],
  'demo-hr': [{ db_connection_uuid: 'demo-hr-db', conn_name: 'hr-warehouse' }],
  'demo-parking': [{ db_connection_uuid: 'demo-commerce-db', conn_name: 'commerce-db' }]
}

const demoSnapshotsByProject: Record<string, Snapshot[]> = {
  'demo-shopping': [
    { schema_snapshot_uuid: 'demo-shopping-snapshot', status: 'succeeded', schema_filter: 'public' }
  ],
  'demo-hr': [
    { schema_snapshot_uuid: 'demo-hr-snapshot', status: 'succeeded', schema_filter: 'hr' }
  ],
  'demo-parking': [
    { schema_snapshot_uuid: 'demo-commerce-snapshot', status: 'succeeded', schema_filter: 'sales' }
  ]
}

const demoDiagramViewsByProject: Record<string, DiagramViewDetail[]> = {}

const demoSnapshotJson: SnapshotJson = {
  relations: [
    { relation_oid: 1, relation_kind: 'r', schema_name: 'public', relation_name: 'member', relation_comment: '회원' },
    { relation_oid: 2, relation_kind: 'r', schema_name: 'public', relation_name: 'orders', relation_comment: '주문' },
    { relation_oid: 3, relation_kind: 'r', schema_name: 'public', relation_name: 'order_item', relation_comment: '주문 상세' }
  ],
  columns: [
    { relation_oid: 1, column_name: 'member_id', data_type: 'bigint', is_not_null: true },
    { relation_oid: 1, column_name: 'email', data_type: 'varchar(255)', is_not_null: true },
    { relation_oid: 2, column_name: 'order_id', data_type: 'bigint', is_not_null: true },
    { relation_oid: 2, column_name: 'member_id', data_type: 'bigint', is_not_null: true },
    { relation_oid: 3, column_name: 'order_item_id', data_type: 'bigint', is_not_null: true },
    { relation_oid: 3, column_name: 'order_id', data_type: 'bigint', is_not_null: true }
  ],
  pk_columns: [
    { relation_oid: 1, column_name: 'member_id' },
    { relation_oid: 2, column_name: 'order_id' },
    { relation_oid: 3, column_name: 'order_item_id' }
  ],
  fk_edges: [
    {
      fk_constraint_oid: 10,
      fk_constraint_name: 'fk_orders_member',
      child_relation_oid: 2,
      parent_relation_oid: 1,
      child_column_name: 'member_id',
      parent_column_name: 'member_id',
      column_ordinal: 1
    },
    {
      fk_constraint_oid: 11,
      fk_constraint_name: 'fk_order_item_order',
      child_relation_oid: 3,
      parent_relation_oid: 2,
      child_column_name: 'order_id',
      parent_column_name: 'order_id',
      column_ordinal: 1
    }
  ]
}

type CsrfTokenResponse = {
  csrf_token: string
}

type ShareLinkResponse = Omit<ShareLink, 'url'>

function isLocalDevelopmentHost(hostname: string): boolean {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname === '::1' ||
    hostname === '[::1]'
  )
}

function requireSecureCredentialTransport(): void {
  const targetUrl = new URL(API_BASE || window.location.origin, window.location.origin)
  if (targetUrl.protocol !== 'https:' && !isLocalDevelopmentHost(targetUrl.hostname)) {
    throw new Error('createConnection requires HTTPS for credential transport')
  }
}

function cloneDiagramViewLayout(layout: DiagramViewLayout): DiagramViewLayout {
  return structuredClone(layout)
}

function diagramViewSummary(view: DiagramViewDetail): DiagramView {
  return {
    diagram_view_uuid: view.diagram_view_uuid,
    name: view.name,
    created_at: view.created_at,
    updated_at: view.updated_at,
  }
}

function findDemoDiagramView(
  diagramViewId: string,
): { projectId: string; index: number; view: DiagramViewDetail } | null {
  for (const [projectId, views] of Object.entries(demoDiagramViewsByProject)) {
    const index = views.findIndex(
      (view) => view.diagram_view_uuid === diagramViewId,
    )
    if (index >= 0) {
      return { projectId, index, view: views[index]! }
    }
  }
  return null
}

export function shareLinkUrlFromPath(urlPath: unknown): string {
  if (typeof urlPath !== 'string' || !urlPath.startsWith('/api/share/')) {
    throw new Error('createShareLink failed: invalid share URL path')
  }

  const apiBase = new URL(API_BASE || window.location.origin, window.location.origin)
  return new URL(urlPath, apiBase).toString()
}

async function csrfToken(): Promise<string> {
  const r = await fetch(`${API_BASE}/api/csrf-token`, {
    credentials: 'include'
  })
  if (!r.ok) throw new Error(`csrfToken failed: ${r.status}`)

  const payload = (await r.json()) as Partial<CsrfTokenResponse>
  if (typeof payload.csrf_token !== 'string' || !payload.csrf_token) {
    throw new Error('csrfToken failed: invalid token response')
  }
  return payload.csrf_token
}

async function jsonHeaders(): Promise<Record<string, string>> {
  return {
    'Content-Type': 'application/json',
    'X-CSRF-Token': await csrfToken()
  }
}

export async function getMe(): Promise<{ subject: string; display_name: string | null; user_account_uuid: string }> {
  if (DEMO_MODE) {
    return { subject: 'local', display_name: 'Local Designer', user_account_uuid: 'demo-user' }
  }
  const r = await fetch(`${API_BASE}/api/me`, { credentials: 'include' })
  if (!r.ok) throw new Error(`getMe failed: ${r.status}`)
  return r.json()
}

export async function listProjects(): Promise<Project[]> {
  if (DEMO_MODE) return demoProjects
  const r = await fetch(`${API_BASE}/api/projects`, { credentials: 'include' })
  if (!r.ok) throw new Error(`listProjects failed: ${r.status}`)
  return r.json()
}

export async function createProject(project_name: string): Promise<Project> {
  if (DEMO_MODE) {
    const project = {
      project_space_uuid: `demo-project-${Date.now()}`,
      project_name
    }
    demoProjects = [project, ...demoProjects]
    demoConnectionsByProject[project.project_space_uuid] = []
    demoSnapshotsByProject[project.project_space_uuid] = []
    demoDiagramViewsByProject[project.project_space_uuid] = []
    return project
  }
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
  if (DEMO_MODE) return demoConnectionsByProject[projectId] ?? []
  const r = await fetch(`${API_BASE}/api/connections/by-project/${projectId}`, { credentials: 'include' })
  if (!r.ok) throw new Error(`listConnections failed: ${r.status}`)
  return r.json()
}

export async function createConnection(projectId: string, conn_name: string, dsn: string): Promise<Connection> {
  if (DEMO_MODE) {
    const connection = {
      db_connection_uuid: `demo-conn-${Date.now()}`,
      conn_name
    }
    demoConnectionsByProject[projectId] = [
      connection,
      ...(demoConnectionsByProject[projectId] ?? [])
    ]
    void dsn
    return connection
  }
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
  if (DEMO_MODE) return demoSnapshotsByProject[projectId] ?? []
  const r = await fetch(`${API_BASE}/api/snapshots/by-project/${projectId}`, { credentials: 'include' })
  if (!r.ok) throw new Error(`listSnapshots failed: ${r.status}`)
  return r.json()
}

export async function createSnapshot(projectId: string, db_connection_uuid: string, schema_filter?: string): Promise<Snapshot> {
  if (DEMO_MODE) {
    const snapshot = {
      schema_snapshot_uuid: `demo-snapshot-${Date.now()}`,
      status: 'succeeded',
      schema_filter: schema_filter || null
    }
    demoSnapshotsByProject[projectId] = [
      snapshot,
      ...(demoSnapshotsByProject[projectId] ?? [])
    ]
    void db_connection_uuid
    return snapshot
  }
  const r = await fetch(`${API_BASE}/api/snapshots/by-project/${projectId}`, {
    method: 'POST',
    credentials: 'include',
    headers: await jsonHeaders(),
    body: JSON.stringify({ db_connection_uuid, schema_filter: schema_filter || null })
  })
  if (!r.ok) throw new Error(`createSnapshot failed: ${r.status}`)
  return r.json()
}

export async function listDiagramViews(projectId: string): Promise<DiagramView[]> {
  if (DEMO_MODE) {
    return (demoDiagramViewsByProject[projectId] ?? []).map(diagramViewSummary)
  }
  const r = await fetch(`${API_BASE}/api/diagram-views/by-project/${projectId}`, {
    credentials: 'include',
  })
  if (!r.ok) throw new Error(`listDiagramViews failed: ${r.status}`)
  return r.json()
}

export async function createDiagramView(
  projectId: string,
  name: string,
  layout_json: DiagramViewLayout,
): Promise<DiagramView> {
  if (DEMO_MODE) {
    const now = new Date(Date.now()).toISOString()
    const view: DiagramViewDetail = {
      diagram_view_uuid: `demo-view-${Date.now()}`,
      name,
      layout_json: cloneDiagramViewLayout(layout_json),
      created_at: now,
      updated_at: now,
    }
    demoDiagramViewsByProject[projectId] = [
      view,
      ...(demoDiagramViewsByProject[projectId] ?? []),
    ]
    return diagramViewSummary(view)
  }
  const r = await fetch(`${API_BASE}/api/diagram-views/by-project/${projectId}`, {
    method: 'POST',
    credentials: 'include',
    headers: await jsonHeaders(),
    body: JSON.stringify({ name, layout_json }),
  })
  if (!r.ok) throw new Error(`createDiagramView failed: ${r.status}`)
  return r.json()
}

export async function getDiagramView(
  diagramViewId: string,
): Promise<DiagramViewDetail> {
  if (DEMO_MODE) {
    const found = findDemoDiagramView(diagramViewId)
    if (!found) throw new Error('getDiagramView failed: 404')
    return {
      ...diagramViewSummary(found.view),
      layout_json: cloneDiagramViewLayout(found.view.layout_json),
    }
  }
  const r = await fetch(`${API_BASE}/api/diagram-views/${diagramViewId}`, {
    credentials: 'include',
  })
  if (!r.ok) throw new Error(`getDiagramView failed: ${r.status}`)
  return r.json()
}

export async function updateDiagramView(
  diagramViewId: string,
  name: string,
  layout_json: DiagramViewLayout,
): Promise<DiagramView> {
  if (DEMO_MODE) {
    const found = findDemoDiagramView(diagramViewId)
    if (!found) throw new Error('updateDiagramView failed: 404')
    const updated: DiagramViewDetail = {
      ...found.view,
      name,
      layout_json: cloneDiagramViewLayout(layout_json),
      updated_at: new Date(Date.now()).toISOString(),
    }
    demoDiagramViewsByProject[found.projectId]![found.index] = updated
    return diagramViewSummary(updated)
  }
  const r = await fetch(`${API_BASE}/api/diagram-views/${diagramViewId}`, {
    method: 'PUT',
    credentials: 'include',
    headers: await jsonHeaders(),
    body: JSON.stringify({ name, layout_json }),
  })
  if (!r.ok) throw new Error(`updateDiagramView failed: ${r.status}`)
  return r.json()
}

export async function deleteDiagramView(diagramViewId: string): Promise<void> {
  if (DEMO_MODE) {
    const found = findDemoDiagramView(diagramViewId)
    if (!found) throw new Error('deleteDiagramView failed: 404')
    demoDiagramViewsByProject[found.projectId]!.splice(found.index, 1)
    return
  }
  const r = await fetch(`${API_BASE}/api/diagram-views/${diagramViewId}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: await jsonHeaders(),
  })
  if (!r.ok) throw new Error(`deleteDiagramView failed: ${r.status}`)
}

export async function createShareLink(projectId: string): Promise<ShareLink> {
  if (DEMO_MODE) {
    return {
      share_link_uuid: `demo-share-${Date.now()}`,
      permission_kind: 'read',
      url_path: `/api/share/demo-${projectId}`,
      url: shareLinkUrlFromPath(`/api/share/demo-${projectId}`)
    }
  }

  const r = await fetch(`${API_BASE}/api/projects/${projectId}/share-links`, {
    method: 'POST',
    credentials: 'include',
    headers: await jsonHeaders()
  })
  if (!r.ok) throw new Error(`createShareLink failed: ${r.status}`)

  const response = (await r.json()) as ShareLinkResponse
  return {
    ...response,
    url: shareLinkUrlFromPath(response.url_path)
  }
}

export async function getSnapshot(snapshotId: string): Promise<SnapshotDetail> {
  if (DEMO_MODE) {
    return {
      schema_snapshot_uuid: snapshotId,
      status: 'succeeded',
      schema_filter: 'public',
      error_message: null,
      snapshot_json: demoSnapshotJson
    }
  }
  const r = await fetch(`${API_BASE}/api/snapshots/${snapshotId}`, { credentials: 'include' })
  if (!r.ok) throw new Error(`getSnapshot failed: ${r.status}`)
  const response = (await r.json()) as SnapshotDetailResponse
  return snapshotDetailFromResponse(response)
}
