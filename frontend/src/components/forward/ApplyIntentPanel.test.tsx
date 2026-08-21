import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MigrationPlan, MigrationRun } from '../../types'
import { ApplyIntentPanel } from './ApplyIntentPanel'

function response(payload: unknown, ok = true, status = ok ? 200 : 500): Response {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, reject, resolve }
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

const passedRun: MigrationRun = {
  migration_run_uuid: 'dry-run-1',
  project_space_uuid: 'project-1',
  migration_plan_uuid: 'plan-1',
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
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => 'request-uuid') })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ApplyIntentPanel', () => {
  it('submits only exact reviewed evidence and an explicitly typed target name', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(response({
        migration_run_uuid: 'apply-intent-1',
        state: 'queued',
        state_version: 1,
        cancellation_requested: false,
        reused: false,
      }, true, 202))
    const onRunCreated = vi.fn()

    render(<ApplyIntentPanel plan={plan} passedDryRun={passedRun} onRunCreated={onRunCreated} />)

    const submit = screen.getByRole('button', { name: '비실행 apply 의도 등록' })
    expect(submit).toBeDisabled()
    fireEvent.change(screen.getByLabelText('대상 연결 이름 확인'), {
      target: { value: 'production-primary' },
    })
    expect(submit).toBeEnabled()
    fireEvent.click(submit)

    await waitFor(() => expect(onRunCreated).toHaveBeenCalledWith('apply-intent-1'))
    expect(fetch).toHaveBeenNthCalledWith(2, '/api/migration-plans/plan-1/apply-runs', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': 'csrf',
        'Idempotency-Key': 'web-apply-intent-request-uuid',
      },
      body: JSON.stringify({
        plan_digest: plan.plan_digest,
        passed_dry_run_uuid: passedRun.migration_run_uuid,
        target_connection_name: 'production-primary',
        destructive_acknowledged: false,
      }),
    })
    expect(String(vi.mocked(fetch).mock.calls[1]?.[1]?.body)).not.toContain('sql')
    expect(screen.getByRole('status')).toHaveTextContent('apply-intent-1')
  })

  it('trims the target name and rejects a whitespace-only confirmation', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(response({
        migration_run_uuid: 'apply-intent-trimmed',
        state: 'queued',
        state_version: 1,
        cancellation_requested: false,
        reused: false,
      }, true, 202))

    render(<ApplyIntentPanel plan={plan} passedDryRun={passedRun} onRunCreated={vi.fn()} />)
    const input = screen.getByLabelText('대상 연결 이름 확인')
    const submit = screen.getByRole('button', { name: '비실행 apply 의도 등록' })
    fireEvent.change(input, { target: { value: '   ' } })
    expect(submit).toBeDisabled()

    fireEvent.change(input, { target: { value: '  production-primary  ' } })
    fireEvent.click(submit)

    await screen.findByRole('status')
    expect(vi.mocked(fetch).mock.calls[1]?.[1]?.body).toContain(
      '"target_connection_name":"production-primary"',
    )
  })

  it('requires an explicit destructive acknowledgement only for destructive plans', () => {
    render(
      <ApplyIntentPanel
        plan={{ ...plan, requires_destructive_confirmation: true }}
        passedDryRun={passedRun}
        onRunCreated={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByLabelText('대상 연결 이름 확인'), {
      target: { value: 'production-primary' },
    })
    const submit = screen.getByRole('button', { name: '비실행 apply 의도 등록' })
    expect(submit).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: '파괴적 변경을 검토하고 확인했습니다.' }))
    expect(submit).toBeEnabled()
  })

  it('keeps direct form submission single-flight and complete for destructive plans', async () => {
    const csrf = deferred<Response>()
    const creation = deferred<Response>()
    vi.mocked(fetch)
      .mockReturnValueOnce(csrf.promise)
      .mockReturnValueOnce(creation.promise)
    const onRunCreated = vi.fn()
    render(
      <ApplyIntentPanel
        plan={{ ...plan, requires_destructive_confirmation: true }}
        passedDryRun={passedRun}
        onRunCreated={onRunCreated}
      />,
    )
    const form = screen.getByRole('button', { name: '비실행 apply 의도 등록' }).closest('form')
    if (!form) throw new Error('apply intent form missing')

    fireEvent.submit(form)
    expect(fetch).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('대상 연결 이름 확인'), {
      target: { value: 'production-primary' },
    })
    fireEvent.submit(form)
    expect(fetch).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('checkbox', { name: '파괴적 변경을 검토하고 확인했습니다.' }))
    fireEvent.submit(form)
    fireEvent.submit(form)
    expect(fetch).toHaveBeenCalledTimes(1)

    csrf.resolve(response({ csrf_token: 'csrf' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    creation.resolve(response({
      migration_run_uuid: 'destructive-intent',
      state: 'queued',
      state_version: 1,
      cancellation_requested: false,
      reused: false,
    }, true, 202))
    await waitFor(() => expect(onRunCreated).toHaveBeenCalledWith('destructive-intent'))
    expect(vi.mocked(fetch).mock.calls[1]?.[1]?.body).toContain(
      '"destructive_acknowledged":true',
    )
  })

  it.each([
    ['non-passed state', { state: 'queued' }],
    ['wrong run kind', { run_kind: 'apply' }],
    ['different plan', { migration_plan_uuid: 'plan-other' }],
    ['different digest', { plan_digest: 'd'.repeat(64) }],
    ['different observed base', { observed_base_digest: 'e'.repeat(64) }],
  ])('fails closed for %s', (_label, override) => {
    render(
      <ApplyIntentPanel
        plan={plan}
        passedDryRun={{ ...passedRun, ...override } as MigrationRun}
        onRunCreated={vi.fn()}
      />,
    )

    expect(screen.getByText('apply 의도를 등록할 수 없습니다.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('retries an ambiguous response with the same bounded idempotency key', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf-1' }))
      .mockResolvedValueOnce(response({}, false, 503))
      .mockResolvedValueOnce(response({ csrf_token: 'csrf-2' }))
      .mockResolvedValueOnce(response({
        migration_run_uuid: 'apply-intent-reused',
        state: 'queued',
        state_version: 1,
        cancellation_requested: false,
        reused: true,
      }, true, 202))

    render(<ApplyIntentPanel plan={plan} passedDryRun={passedRun} onRunCreated={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('대상 연결 이름 확인'), {
      target: { value: 'production-primary' },
    })
    fireEvent.click(screen.getByRole('button', { name: '비실행 apply 의도 등록' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('등록 결과를 확인하지 못했습니다')
    expect(alert).not.toHaveTextContent(/503|secret/)
    expect(screen.getByLabelText('대상 연결 이름 확인')).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '같은 등록 다시 시도' }))

    expect(await screen.findByRole('status')).toHaveTextContent('기존 등록을 재사용했습니다')
    const firstKey = (vi.mocked(fetch).mock.calls[1]?.[1]?.headers as Record<string, string>)[
      'Idempotency-Key'
    ]
    const retryKey = (vi.mocked(fetch).mock.calls[3]?.[1]?.headers as Record<string, string>)[
      'Idempotency-Key'
    ]
    expect(firstKey).toBe('web-apply-intent-request-uuid')
    expect(retryKey).toBe(firstKey)
    expect(vi.mocked(fetch).mock.calls[3]?.[1]?.body)
      .toBe(vi.mocked(fetch).mock.calls[1]?.[1]?.body)
  })

  it('unlocks an ambiguous intent only through an explicit new registration', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf-1' }))
      .mockResolvedValueOnce(response({}, false, 503))
      .mockResolvedValueOnce(response({ csrf_token: 'csrf-2' }))
      .mockResolvedValueOnce(response({
        migration_run_uuid: 'apply-intent-new',
        state: 'queued',
        state_version: 1,
        cancellation_requested: false,
        reused: false,
      }, true, 202))
    vi.mocked(crypto.randomUUID)
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000001')
      .mockReturnValueOnce('00000000-0000-4000-8000-000000000002')

    render(<ApplyIntentPanel plan={plan} passedDryRun={passedRun} onRunCreated={vi.fn()} />)
    const input = screen.getByLabelText('대상 연결 이름 확인')
    fireEvent.change(input, { target: { value: 'production-primary' } })
    fireEvent.click(screen.getByRole('button', { name: '비실행 apply 의도 등록' }))

    await screen.findByRole('alert')
    expect(input).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '새 등록 시작' }))
    expect(input).toBeEnabled()
    fireEvent.change(input, { target: { value: 'production-secondary' } })
    fireEvent.click(screen.getByRole('button', { name: '비실행 apply 의도 등록' }))

    await screen.findByRole('status')
    const firstHeaders = vi.mocked(fetch).mock.calls[1]?.[1]?.headers as Record<string, string>
    const secondHeaders = vi.mocked(fetch).mock.calls[3]?.[1]?.headers as Record<string, string>
    expect(firstHeaders['Idempotency-Key'])
      .toBe('web-apply-intent-00000000-0000-4000-8000-000000000001')
    expect(secondHeaders['Idempotency-Key'])
      .toBe('web-apply-intent-00000000-0000-4000-8000-000000000002')
    expect(vi.mocked(fetch).mock.calls[3]?.[1]?.body).toContain('production-secondary')
  })

  it('ignores an obsolete accepted response after the reviewed identities change', async () => {
    const accepted = deferred<Response>()
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockReturnValueOnce(accepted.promise)
    const onRunCreated = vi.fn()
    const { rerender } = render(
      <ApplyIntentPanel plan={plan} passedDryRun={passedRun} onRunCreated={onRunCreated} />,
    )

    fireEvent.change(screen.getByLabelText('대상 연결 이름 확인'), {
      target: { value: 'production-primary' },
    })
    fireEvent.click(screen.getByRole('button', { name: '비실행 apply 의도 등록' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    rerender(
      <ApplyIntentPanel
        plan={{ ...plan, migration_plan_uuid: 'plan-2', plan_digest: 'd'.repeat(64) }}
        passedDryRun={{
          ...passedRun,
          migration_plan_uuid: 'plan-2',
          migration_run_uuid: 'dry-run-2',
          plan_digest: 'd'.repeat(64),
        }}
        onRunCreated={onRunCreated}
      />,
    )
    accepted.resolve(response({
      migration_run_uuid: 'obsolete-apply-intent',
      state: 'queued',
      state_version: 1,
      cancellation_requested: false,
      reused: false,
    }, true, 202))

    await accepted.promise
    await waitFor(() => expect(onRunCreated).not.toHaveBeenCalled())
    expect(screen.queryByText('obsolete-apply-intent')).not.toBeInTheDocument()
  })

  it('ignores an obsolete failure after the reviewed identities change', async () => {
    const accepted = deferred<Response>()
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockReturnValueOnce(accepted.promise)
    const { rerender } = render(
      <ApplyIntentPanel plan={plan} passedDryRun={passedRun} onRunCreated={vi.fn()} />,
    )

    fireEvent.change(screen.getByLabelText('대상 연결 이름 확인'), {
      target: { value: 'production-primary' },
    })
    fireEvent.click(screen.getByRole('button', { name: '비실행 apply 의도 등록' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    rerender(
      <ApplyIntentPanel
        plan={{ ...plan, migration_plan_uuid: 'plan-2', plan_digest: 'd'.repeat(64) }}
        passedDryRun={{
          ...passedRun,
          migration_plan_uuid: 'plan-2',
          migration_run_uuid: 'dry-run-2',
          plan_digest: 'd'.repeat(64),
        }}
        onRunCreated={vi.fn()}
      />,
    )
    accepted.reject(new Error('obsolete failure with secret'))

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: '비실행 apply 의도 등록' })).toBeDisabled()
    })
  })

  it('fails closed when the browser cannot generate an apply intent identity', async () => {
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn(() => {
        throw new Error('browser diagnostic with secret')
      }),
    })
    render(<ApplyIntentPanel plan={plan} passedDryRun={passedRun} onRunCreated={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('대상 연결 이름 확인'), {
      target: { value: 'production-primary' },
    })
    fireEvent.click(screen.getByRole('button', { name: '비실행 apply 의도 등록' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('등록 결과를 확인하지 못했습니다')
    expect(alert).not.toHaveTextContent('secret')
    expect(fetch).not.toHaveBeenCalled()
  })
})
