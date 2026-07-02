import { snapshotDetailFromResponse } from './types'
import type { Connection, Project, ShareLink, Snapshot, SnapshotDetail, SnapshotDetailResponse, SnapshotJson } from './types'

// Default to same-origin in production; set VITE_API_BASE_URL for dev.
const API_BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'
const DEMO_EMPTY_WORKSPACE_QUERY = 'demo-workspace'
const DEMO_SUPPORT_QUERY = 'demo-support'

type ApiErrorOptions = {
  accountStatus?: string | null
  accountReactivationUrl?: string | null
  billingSupportUrl?: string | null
}

export class ApiError extends Error {
  readonly operation: string
  readonly status: number
  readonly accountStatus: string | null
  readonly accountReactivationUrl: string | null
  readonly billingSupportUrl: string | null

  constructor(operation: string, status: number, options: ApiErrorOptions = {}) {
    super(`${operation} failed: ${status}`)
    this.name = 'ApiError'
    this.operation = operation
    this.status = status
    this.accountStatus = options.accountStatus ?? null
    this.accountReactivationUrl = options.accountReactivationUrl ?? null
    this.billingSupportUrl = options.billingSupportUrl ?? null
  }
}

function apiErrorFromResponse(operation: string, response: Response): ApiError {
  return new ApiError(operation, response.status, {
    accountStatus: response.headers.get('X-Account-Status'),
    accountReactivationUrl: response.headers.get('X-Account-Reactivation-Url'),
    billingSupportUrl: response.headers.get('X-Billing-Support-Url')
  })
}

function isDemoEmptyWorkspace(): boolean {
  if (!DEMO_MODE || typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).get(DEMO_EMPTY_WORKSPACE_QUERY) === 'empty'
}

function isDemoSupportOperator(): boolean {
  if (!DEMO_MODE || typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).get(DEMO_SUPPORT_QUERY) === 'operator'
}

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

export type CurrentUser = {
  user_account_uuid: string
  subject: string
  display_name: string | null
  support_operator: boolean
}

export type BillingEventSummary = {
  billing_event_uuid: string
  provider: string
  provider_event_id: string
  event_type: string
  target_plan: string | null
  status: 'recorded'
  occurred_at: string
  received_at: string
}

export type BillingSupportShareLinkSummary = {
  share_link_uuid: string
  project_space_uuid: string
  permission_kind: string
  status: 'active' | 'expired'
  expires_at: string | null
  created_at: string
}

export type BillingSupportAccount = {
  subject: string
  user_account_uuid: string | null
  account_status: 'active' | 'deactivated' | 'unknown'
  license_mode: 'off' | 'required'
  license_verifier: 'none' | 'static_key' | 'signed_token' | 'static_key_and_signed_token'
  billing_portal_url: string | null
  billing_support_url: string | null
  account_reactivation_url: string | null
  project_count: number
  seat_count: number
  connection_count: number
  snapshot_count: number
  share_link_count: number
  active_share_link_count: number
  recent_share_links: BillingSupportShareLinkSummary[]
  recent_billing_events: BillingEventSummary[]
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

export async function getMe(): Promise<CurrentUser> {
  if (DEMO_MODE) {
    return {
      subject: 'local',
      display_name: 'Local Designer',
      user_account_uuid: 'demo-user',
      support_operator: isDemoSupportOperator()
    }
  }
  const r = await fetch(`${API_BASE}/api/me`, { credentials: 'include' })
  if (!r.ok) throw apiErrorFromResponse('getMe', r)
  return r.json()
}

export async function getBillingSupportAccount(subject: string): Promise<BillingSupportAccount> {
  if (DEMO_MODE) {
    const demoSubject = subject || 'customer-owner'
    if (demoSubject.toLowerCase().includes('stress')) {
      return {
        subject: demoSubject,
        user_account_uuid: 'demo-customer-user-with-long-contract-history',
        account_status: 'active',
        license_mode: 'required',
        license_verifier: 'signed_token',
        billing_portal_url:
          'https://billing.example.com/customer/demo-customer-user-with-long-contract-history',
        billing_support_url: 'https://support.example.com/billing/enterprise-contracts/apac-ko',
        account_reactivation_url:
          'https://billing.example.com/reactivate/demo-customer-user-with-long-contract-history',
        project_count: 12,
        seat_count: 250,
        connection_count: 44,
        snapshot_count: 128,
        share_link_count: 31,
        active_share_link_count: 9,
        recent_share_links: [
          {
            share_link_uuid:
              'demo-share-active-enterprise-private-network-review-2026-07-02-long-id',
            project_space_uuid:
              'demo-project-enterprise-data-warehouse-private-network-apac-ko-01',
            permission_kind: 'viewer',
            status: 'active',
            expires_at: '2026-12-31T23:59:59Z',
            created_at: '2026-07-02T00:05:00Z'
          }
        ],
        recent_billing_events: [
          {
            billing_event_uuid: 'demo-billing-event-stress-1',
            provider: 'enterprise-contracting-system-apac-ko-very-long-provider-code',
            provider_event_id:
              'contract-2026-07-private-network-renewal-krw-2b-evaluation-001',
            event_type: 'contract.lifecycle.enterprise_plus_private_onprem_renewal_completed',
            target_plan: 'onprem-enterprise-plus-krw-2b-evaluation-with-private-network-addon',
            status: 'recorded',
            occurred_at: '2026-07-02T00:00:00Z',
            received_at: '2026-07-02T00:01:22Z'
          }
        ]
      }
    }
    return {
      subject: demoSubject,
      user_account_uuid: 'demo-customer-user',
      account_status: 'active',
      license_mode: 'required',
      license_verifier: 'signed_token',
      billing_portal_url: 'https://billing.example.com/customer/demo-customer-user',
      billing_support_url: 'https://support.example.com/billing',
      account_reactivation_url: 'https://billing.example.com/reactivate/demo-customer-user',
      project_count: 3,
      seat_count: 12,
      connection_count: 4,
      snapshot_count: 18,
      share_link_count: 7,
      active_share_link_count: 2,
      recent_share_links: [
        {
          share_link_uuid: 'demo-share-active-1',
          project_space_uuid: 'demo-project-warehouse',
          permission_kind: 'viewer',
          status: 'active',
          expires_at: '2026-07-09T00:00:00Z',
          created_at: '2026-07-02T00:05:00Z'
        },
        {
          share_link_uuid: 'demo-share-expired-1',
          project_space_uuid: 'demo-project-archive',
          permission_kind: 'viewer',
          status: 'expired',
          expires_at: '2026-06-25T00:00:00Z',
          created_at: '2026-06-18T00:05:00Z'
        }
      ],
      recent_billing_events: [
        {
          billing_event_uuid: 'demo-billing-event-1',
          provider: 'stripe',
          provider_event_id: 'evt_demo_subscription_updated',
          event_type: 'subscription.updated',
          target_plan: 'enterprise',
          status: 'recorded',
          occurred_at: '2026-07-02T00:00:00Z',
          received_at: '2026-07-02T00:01:22Z'
        },
        {
          billing_event_uuid: 'demo-billing-event-2',
          provider: 'manual-contract',
          provider_event_id: 'contract-demo-renewal',
          event_type: 'contract.renewed',
          target_plan: 'onprem-enterprise',
          status: 'recorded',
          occurred_at: '2026-07-01T09:00:00Z',
          received_at: '2026-07-01T09:03:11Z'
        }
      ]
    }
  }

  const query = new URLSearchParams({ subject })
  const r = await fetch(`${API_BASE}/api/billing/support/account?${query.toString()}`, {
    credentials: 'include'
  })
  if (!r.ok) throw new Error(`getBillingSupportAccount failed: ${r.status}`)
  return r.json()
}

export async function listProjects(): Promise<Project[]> {
  if (isDemoEmptyWorkspace()) return []
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
