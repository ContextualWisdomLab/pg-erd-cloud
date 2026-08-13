import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MigrationPlan } from '../../types'
import { DryRunIntentPanel } from './DryRunIntentPanel'

function response(payload: unknown, ok = true, status = ok ? 200 : 500): Response {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

const plan: MigrationPlan = {
  migration_plan_uuid: 'plan-1',
  project_space_uuid: 'project-1',
  schema_model_revision_uuid: 'revision-1',
  db_connection_uuid: 'connection-1',
  base_schema_snapshot_uuid: 'snapshot-1',
  plan_digest: 'a'.repeat(64),
  base_digest: 'b'.repeat(64),
  target_digest: 'c'.repeat(64),
  compiler_version: 'pg-plan-v1',
  snapshot_contract_version: 1,
  postgresql_major: 16,
  created_by_user_uuid: 'user-1',
  created_at: '2026-08-12T05:00:00Z',
  can_dry_run: true,
  requires_destructive_confirmation: false,
  statements: [],
  proposed_statements: [],
  blockers: [],
  risk_summary: { safe: 0, warning: 0, destructive: 0 },
  expires_at: '2026-08-13T05:00:00Z',
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => 'request-uuid') })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('DryRunIntentPanel', () => {
  it('submits only the server plan identity and exact digest, then returns the durable run', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(response({
        migration_run_uuid: 'run-1',
        state: 'queued',
        state_version: 1,
        cancellation_requested: false,
        reused: false,
      }, true, 202))
    const onRunCreated = vi.fn()

    render(<DryRunIntentPanel plan={plan} onRunCreated={onRunCreated} />)
    fireEvent.click(screen.getByRole('button', { name: '격리 dry-run 요청' }))

    await waitFor(() => expect(onRunCreated).toHaveBeenCalledWith('run-1'))
    expect(fetch).toHaveBeenNthCalledWith(2, '/api/migration-plans/plan-1/dry-runs', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': 'csrf',
        'Idempotency-Key': 'web-dry-run-request-uuid',
      },
      body: JSON.stringify({ plan_digest: plan.plan_digest }),
    })
    expect(String(vi.mocked(fetch).mock.calls[1]?.[1]?.body)).not.toContain('sql')
    expect(screen.getByRole('status')).toHaveTextContent('run-1')
  })

  it('allows only one in-flight request when the action is activated repeatedly', async () => {
    const csrf = deferred<Response>()
    vi.mocked(fetch).mockReturnValueOnce(csrf.promise)

    render(<DryRunIntentPanel plan={plan} onRunCreated={vi.fn()} />)
    const button = screen.getByRole('button', { name: '격리 dry-run 요청' })
    fireEvent.click(button)
    fireEvent.click(button)

    expect(button).toBeDisabled()
    expect(fetch).toHaveBeenCalledTimes(1)
    csrf.resolve(response({ csrf_token: 'csrf' }))
    await waitFor(() => expect(button).not.toBeDisabled())
  })

  it('retries an ambiguous failure with the same bounded idempotency key', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf-1' }))
      .mockResolvedValueOnce(response({}, false, 503))
      .mockResolvedValueOnce(response({ csrf_token: 'csrf-2' }))
      .mockResolvedValueOnce(response({
        migration_run_uuid: 'run-reused',
        state: 'queued',
        state_version: 1,
        cancellation_requested: false,
        reused: true,
      }, true, 202))

    render(<DryRunIntentPanel plan={plan} onRunCreated={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: '격리 dry-run 요청' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('요청 결과를 확인하지 못했습니다')
    expect(alert).not.toHaveTextContent(/503|createDryRun|secret/)
    fireEvent.click(screen.getByRole('button', { name: '같은 요청 다시 시도' }))

    expect(await screen.findByRole('status')).toHaveTextContent('기존 요청을 재사용했습니다')
    const firstKey = (vi.mocked(fetch).mock.calls[1]?.[1]?.headers as Record<string, string>)[
      'Idempotency-Key'
    ]
    const retryKey = (vi.mocked(fetch).mock.calls[3]?.[1]?.headers as Record<string, string>)[
      'Idempotency-Key'
    ]
    expect(firstKey).toBe('web-dry-run-request-uuid')
    expect(retryKey).toBe(firstKey)
  })

  it('does not expose an action when the server marks the plan as blocked', () => {
    render(
      <DryRunIntentPanel
        plan={{
          ...plan,
          can_dry_run: false,
          blockers: [{
            code: 'unsupported_object',
            object: 'public.v',
            object_ref: {
              database: null,
              schema_name: 'public',
              table_name: 'v',
              column_name: null,
            },
            detail: 'view is unsupported',
          }],
        }}
        onRunCreated={vi.fn()}
      />,
    )

    expect(screen.getByText('격리 dry-run을 요청할 수 없습니다.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('ignores an obsolete accepted response after the reviewed plan changes', async () => {
    const accepted = deferred<Response>()
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockReturnValueOnce(accepted.promise)
    const onRunCreated = vi.fn()
    const { rerender } = render(
      <DryRunIntentPanel plan={plan} onRunCreated={onRunCreated} />,
    )

    fireEvent.click(screen.getByRole('button', { name: '격리 dry-run 요청' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    rerender(
      <DryRunIntentPanel
        plan={{
          ...plan,
          migration_plan_uuid: 'plan-2',
          plan_digest: 'd'.repeat(64),
        }}
        onRunCreated={onRunCreated}
      />,
    )
    accepted.resolve(response({
      migration_run_uuid: 'obsolete-run',
      state: 'queued',
      state_version: 1,
      cancellation_requested: false,
      reused: false,
    }, true, 202))

    await accepted.promise
    await waitFor(() => {
      expect(onRunCreated).not.toHaveBeenCalled()
      expect(screen.getByRole('button', { name: '격리 dry-run 요청' })).toBeEnabled()
    })
    expect(screen.queryByText('obsolete-run')).not.toBeInTheDocument()
  })

  it('fails closed when a browser cannot generate a request identity', async () => {
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn(() => {
        throw new Error('browser diagnostic with secret')
      }),
    })

    render(<DryRunIntentPanel plan={plan} onRunCreated={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: '격리 dry-run 요청' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('요청 결과를 확인하지 못했습니다')
    expect(alert).not.toHaveTextContent('secret')
    expect(fetch).not.toHaveBeenCalled()
  })
})
