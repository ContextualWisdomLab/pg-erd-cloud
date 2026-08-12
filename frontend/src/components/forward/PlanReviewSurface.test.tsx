import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MigrationPlan } from '../../types'
import { PlanReviewSurface } from './index'

function response(payload: unknown, ok = true, status = ok ? 200 : 500): Response {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function plan(id: string): MigrationPlan {
  return {
    migration_plan_uuid: id,
    project_space_uuid: '22222222-2222-4222-8222-222222222222',
    schema_model_revision_uuid: '33333333-3333-4333-8333-333333333333',
    db_connection_uuid: '44444444-4444-4444-8444-444444444444',
    base_schema_snapshot_uuid: '55555555-5555-4555-8555-555555555555',
    plan_digest: 'a'.repeat(64),
    base_digest: 'b'.repeat(64),
    target_digest: 'c'.repeat(64),
    compiler_version: 'pg-plan-v1',
    snapshot_contract_version: 1,
    postgresql_major: 16,
    created_by_user_uuid: '66666666-6666-4666-8666-666666666666',
    created_at: '2026-08-12T05:00:00Z',
    can_dry_run: true,
    requires_destructive_confirmation: false,
    statements: [],
    proposed_statements: [],
    blockers: [],
    risk_summary: { safe: 0, warning: 0, destructive: 0 },
    expires_at: '2026-08-13T05:00:00Z',
  }
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('PlanReviewSurface', () => {
  it('announces loading and renders the exact immutable plan', async () => {
    vi.mocked(fetch).mockResolvedValue(response(plan('plan-1')))

    render(<PlanReviewSurface planId="plan-1" />)

    expect(screen.getByRole('status')).toHaveTextContent('계획을 불러오는 중입니다')
    expect(await screen.findByText('plan-1')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/migration-plans/plan-1', {
      credentials: 'include',
    })
  })

  it('shows a fixed safe error and retries without exposing response data', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ detail: 'dsn=postgres://secret@host' }, false, 503))
      .mockResolvedValueOnce(response(plan('plan-retry')))

    render(<PlanReviewSurface planId="plan-retry" />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('계획을 불러오지 못했습니다')
    expect(alert).not.toHaveTextContent('secret')
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }))

    expect(await screen.findByText('plan-retry')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('ignores an obsolete response after the requested plan changes', async () => {
    let resolveFirst!: (value: Response) => void
    const first = new Promise<Response>((resolve) => {
      resolveFirst = resolve
    })
    vi.mocked(fetch)
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce(response(plan('plan-current')))

    const { rerender } = render(<PlanReviewSurface planId="plan-obsolete" />)
    rerender(<PlanReviewSurface planId="plan-current" />)

    expect(await screen.findByText('plan-current')).toBeInTheDocument()
    resolveFirst(response(plan('plan-obsolete')))
    await waitFor(() => expect(screen.queryByText('plan-obsolete')).not.toBeInTheDocument())
  })

  it('ignores an obsolete failure after the requested plan changes', async () => {
    let rejectFirst!: (reason: Error) => void
    const first = new Promise<Response>((_resolve, reject) => {
      rejectFirst = reject
    })
    vi.mocked(fetch)
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce(response(plan('plan-current')))

    const { rerender } = render(<PlanReviewSurface planId="plan-obsolete" />)
    rerender(<PlanReviewSurface planId="plan-current" />)

    expect(await screen.findByText('plan-current')).toBeInTheDocument()
    rejectFirst(new Error('obsolete failure with secret response'))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })

  it('hands an accepted exact-digest intent to terminal-aware run polling', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response(plan('plan-run')))
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(response({
        migration_run_uuid: 'run-created',
        state: 'queued',
        state_version: 1,
        cancellation_requested: false,
        reused: false,
      }, true, 202))
      .mockResolvedValueOnce(response({
        migration_run_uuid: 'run-created',
        project_space_uuid: 'project-1',
        migration_plan_uuid: 'plan-run',
        run_kind: 'dry_run',
        state: 'passed',
        state_version: 4,
        plan_digest: 'a'.repeat(64),
        requested_by_user_uuid: 'user-1',
        cancellation_requested: false,
        observed_base_digest: 'b'.repeat(64),
        evidence: {},
        error_code: null,
        created_at: '2026-08-12T05:00:00Z',
        updated_at: '2026-08-12T05:01:00Z',
        started_at: '2026-08-12T05:00:10Z',
        finished_at: '2026-08-12T05:01:00Z',
        events: [],
      }))

    render(<PlanReviewSurface planId="plan-run" />)
    await screen.findByText('plan-run')
    fireEvent.click(screen.getByRole('button', { name: '격리 dry-run 요청' }))

    expect(await screen.findByRole('status', { name: '마이그레이션 실행 상태' }))
      .toHaveTextContent('격리 검증 및 읽기 전용 사전 점검 통과')
    expect(fetch).toHaveBeenNthCalledWith(4, '/api/migration-runs/run-created', {
      credentials: 'include',
    })
  })
})
