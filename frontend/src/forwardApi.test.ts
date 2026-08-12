import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  cancelMigrationRun,
  createApplyRun,
  createDryRun,
  getMigrationPlan,
  getMigrationRun,
} from './api'

function response(payload: unknown, ok = true, status = ok ? 200 : 500): Response {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

describe('Forward Engineering API client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reads immutable plans and durable run evidence with credentials', async () => {
    const fetchMock = vi.mocked(fetch)
    const plan = { migration_plan_uuid: 'plan-1', plan_digest: 'a'.repeat(64) }
    const run = { migration_run_uuid: 'run-1', state: 'queued', events: [] }
    fetchMock.mockResolvedValueOnce(response(plan)).mockResolvedValueOnce(response(run))

    await expect(getMigrationPlan('plan-1')).resolves.toEqual(plan)
    await expect(getMigrationRun('run-1')).resolves.toEqual(run)

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/migration-plans/plan-1', {
      credentials: 'include',
    })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/migration-runs/run-1', {
      credentials: 'include',
    })
  })

  it('encodes resource identifiers as single path segments', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(response({ migration_plan_uuid: 'plan/../other' }))
      .mockResolvedValueOnce(response({ migration_run_uuid: 'run?tenant=other' }))

    await getMigrationPlan('plan/../other')
    await getMigrationRun('run?tenant=other')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/migration-plans/plan%2F..%2Fother',
      { credentials: 'include' },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/migration-runs/run%3Ftenant%3Dother',
      { credentials: 'include' },
    )
  })

  it('creates exact dry-run and apply intents without accepting SQL', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(response({ csrf_token: 'csrf-dry' }))
      .mockResolvedValueOnce(response({ migration_run_uuid: 'dry-1', state: 'queued' }, true, 202))
      .mockResolvedValueOnce(response({ csrf_token: 'csrf-apply' }))
      .mockResolvedValueOnce(response({ migration_run_uuid: 'apply-1', state: 'queued' }, true, 202))

    await createDryRun('plan-1', 'a'.repeat(64), 'dry-request-1')
    await createApplyRun(
      'plan-1',
      {
        plan_digest: 'a'.repeat(64),
        passed_dry_run_uuid: 'dry-1',
        target_connection_name: 'production-readonly',
        destructive_acknowledged: false,
      },
      'apply-request-1',
    )

    const dryRequest = fetchMock.mock.calls[1]
    const applyRequest = fetchMock.mock.calls[3]
    expect(dryRequest).toEqual([
      '/api/migration-plans/plan-1/dry-runs',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': 'csrf-dry',
          'Idempotency-Key': 'dry-request-1',
        },
        body: JSON.stringify({ plan_digest: 'a'.repeat(64) }),
      }),
    ])
    expect(applyRequest).toEqual([
      '/api/migration-plans/plan-1/apply-runs',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': 'csrf-apply',
          'Idempotency-Key': 'apply-request-1',
        },
      }),
    ])
    expect(String(applyRequest?.[1]?.body)).not.toContain('sql')
  })

  it('cancels by exact optimistic state version', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(
        response({
          migration_run_uuid: 'run-1',
          state: 'sandbox_running',
          state_version: 4,
          cancellation_requested: true,
          reused: false,
        }, true, 202),
      )

    await cancelMigrationRun('run-1', 3)

    expect(fetchMock.mock.calls[1]).toEqual([
      '/api/migration-runs/run-1/cancel',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ expected_state_version: 3 }),
      }),
    ])
  })

  it.each([
    ['getMigrationPlan', () => getMigrationPlan('plan-1')],
    ['getMigrationRun', () => getMigrationRun('run-1')],
  ])('reports %s failures using only the HTTP status', async (name, invoke) => {
    vi.mocked(fetch).mockResolvedValue(response({}, false, 409))

    await expect(invoke()).rejects.toThrow(`${name} failed: 409`)
  })

  it.each([
    ['createDryRun', () => createDryRun('plan-1', 'a'.repeat(64), 'dry-request-1')],
    [
      'createApplyRun',
      () => createApplyRun(
        'plan-1',
        {
          plan_digest: 'a'.repeat(64),
          passed_dry_run_uuid: 'dry-1',
          target_connection_name: 'production-readonly',
          destructive_acknowledged: false,
        },
        'apply-request-1',
      ),
    ],
    ['cancelMigrationRun', () => cancelMigrationRun('run-1', 3)],
  ])('reports %s write failures without echoing request data', async (name, invoke) => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(response({}, false, 409))

    await expect(invoke()).rejects.toThrow(`${name} failed: 409`)
  })
})
