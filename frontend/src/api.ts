import { snapshotDetailFromResponse } from './types'
import type { Connection, DiagramView, DiagramViewDetail, Project, SchemaDiff, ShareLink, Snapshot, SnapshotDetail, SnapshotDetailResponse, SnapshotDiffResult, SnapshotJson, ViewLayout } from './types'

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
    { schema_snapshot_uuid: 'demo-shopping-snapshot', status: 'succeeded', schema_filter: 'public' },
    { schema_snapshot_uuid: 'demo-shopping-snapshot-prev', status: 'succeeded', schema_filter: 'public' }
  ],
  'demo-hr': [
    { schema_snapshot_uuid: 'demo-hr-snapshot', status: 'succeeded', schema_filter: 'hr' }
  ],
  'demo-parking': [
    { schema_snapshot_uuid: 'demo-commerce-snapshot', status: 'succeeded', schema_filter: 'sales' }
  ]
}

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
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'
}

function requireSecureCredentialTransport(): void {
  const targetUrl = new URL(API_BASE || window.location.origin, window.location.origin)
  if (targetUrl.protocol !== 'https:' && !isLocalDevelopmentHost(targetUrl.hostname)) {
    throw new Error('createConnection requires HTTPS for credential transport')
  }
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

const demoSchemaDiff: SchemaDiff = {
  base_table_count: 3,
  target_table_count: 4,
  tables: {
    added: ['public.order_item'],
    removed: [],
    changed: [
      {
        table: 'public.member',
        columns: {
          added: ['phone'],
          removed: [],
          changed: [
            {
              column: 'email',
              from: { data_type: 'varchar(100)', is_not_null: false },
              to: { data_type: 'varchar(255)', is_not_null: true }
            }
          ]
        }
      }
    ]
  },
  foreign_keys: {
    added: [
      {
        name: 'fk_order_item_order',
        child_table: 'public.order_item',
        child_columns: ['order_id'],
        parent_table: 'public.orders',
        parent_columns: ['order_id']
      }
    ],
    removed: []
  },
  summary: {
    tables_added: 1,
    tables_removed: 0,
    tables_changed: 1,
    columns_added: 1,
    columns_removed: 0,
    columns_changed: 1,
    fks_added: 1,
    fks_removed: 0,
    has_changes: true
  }
}

export async function diffSnapshots(targetId: string, againstId: string): Promise<SnapshotDiffResult> {
  if (DEMO_MODE) {
    return {
      base_snapshot_uuid: againstId,
      target_snapshot_uuid: targetId,
      status: 'ok',
      diff: demoSchemaDiff
    }
  }
  const params = new URLSearchParams({ against: againstId })
  const r = await fetch(
    `${API_BASE}/api/snapshots/${encodeURIComponent(targetId)}/diff?${params.toString()}`,
    { credentials: 'include' }
  )
  if (!r.ok) throw new Error(`diffSnapshots failed: ${r.status}`)
  return r.json()
}

const demoViewsByProject: Record<string, DiagramViewDetail[]> = {}

export async function listViews(projectId: string): Promise<DiagramView[]> {
  if (DEMO_MODE) {
    return (demoViewsByProject[projectId] ?? []).map(
      ({ layout_json: _layout, ...summary }) => summary
    )
  }
  const r = await fetch(
    `${API_BASE}/api/diagram-views/by-project/${encodeURIComponent(projectId)}`,
    { credentials: 'include' }
  )
  if (!r.ok) throw new Error(`listViews failed: ${r.status}`)
  return r.json()
}

export async function createView(projectId: string, name: string, layout_json: ViewLayout): Promise<DiagramView> {
  if (DEMO_MODE) {
    const now = new Date().toISOString()
    const view: DiagramViewDetail = {
      diagram_view_uuid: `demo-view-${Date.now()}`,
      name,
      created_at: now,
      updated_at: now,
      layout_json
    }
    demoViewsByProject[projectId] = [view, ...(demoViewsByProject[projectId] ?? [])]
    const { layout_json: _layout, ...summary } = view
    return summary
  }
  const r = await fetch(
    `${API_BASE}/api/diagram-views/by-project/${encodeURIComponent(projectId)}`,
    {
      method: 'POST',
      credentials: 'include',
      headers: await jsonHeaders(),
      body: JSON.stringify({ name, layout_json })
    }
  )
  if (!r.ok) throw new Error(`createView failed: ${r.status}`)
  return r.json()
}

export async function getView(viewId: string): Promise<DiagramViewDetail> {
  if (DEMO_MODE) {
    for (const list of Object.values(demoViewsByProject)) {
      const found = list.find((v) => v.diagram_view_uuid === viewId)
      if (found) return found
    }
    throw new Error('getView failed: 404')
  }
  const r = await fetch(
    `${API_BASE}/api/diagram-views/${encodeURIComponent(viewId)}`,
    { credentials: 'include' }
  )
  if (!r.ok) throw new Error(`getView failed: ${r.status}`)
  return r.json()
}

export async function deleteView(viewId: string): Promise<void> {
  if (DEMO_MODE) {
    for (const projectId of Object.keys(demoViewsByProject)) {
      demoViewsByProject[projectId] = demoViewsByProject[projectId].filter(
        (v) => v.diagram_view_uuid !== viewId
      )
    }
    return
  }
  const r = await fetch(
    `${API_BASE}/api/diagram-views/${encodeURIComponent(viewId)}`,
    {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'X-CSRF-Token': await csrfToken() }
    }
  )
  if (!r.ok) throw new Error(`deleteView failed: ${r.status}`)
}
