import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MigrationRun } from '../../types'
import { RunCancellationControl } from './RunCancellationControl'

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

const run: MigrationRun = {
  migration_run_uuid: 'run-1',
  project_space_uuid: 'project-1',
  migration_plan_uuid: 'plan-1',
  run_kind: 'dry_run',
  state: 'sandbox_running',
  state_version: 3,
  plan_digest: 'a'.repeat(64),
  requested_by_user_uuid: 'user-1',
  cancellation_requested: false,
  observed_base_digest: null,
  evidence: {},
  error_code: null,
  created_at: '2026-08-12T05:00:00Z',
  updated_at: '2026-08-12T05:00:10Z',
  started_at: '2026-08-12T05:00:05Z',
  finished_at: null,
  events: [],
}

beforeEach(() => vi.stubGlobal('fetch', vi.fn()))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('RunCancellationControl', () => {
  it('submits one exact optimistic state version and refreshes after acceptance', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(response({
        migration_run_uuid: 'run-1',
        state: 'sandbox_running',
        state_version: 4,
        cancellation_requested: true,
        reused: false,
      }, true, 202))
    const onRefresh = vi.fn()

    render(<RunCancellationControl run={run} onRefresh={onRefresh} />)
    fireEvent.click(screen.getByRole('button', { name: '실행 취소 요청' }))

    await waitFor(() => expect(onRefresh).toHaveBeenCalledOnce())
    expect(fetch).toHaveBeenNthCalledWith(2, '/api/migration-runs/run-1/cancel', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': 'csrf',
      },
      body: JSON.stringify({ expected_state_version: 3 }),
    })
  })

  it('admits only one request while cancellation is in flight', async () => {
    const csrf = deferred<Response>()
    vi.mocked(fetch).mockReturnValueOnce(csrf.promise)

    render(<RunCancellationControl run={run} onRefresh={vi.fn()} />)
    const button = screen.getByRole('button', { name: '실행 취소 요청' })
    fireEvent.click(button)
    fireEvent.click(button)

    expect(button).toBeDisabled()
    expect(fetch).toHaveBeenCalledTimes(1)
    csrf.resolve(response({ csrf_token: 'csrf' }))
  })

  it('keeps the single-flight guard when polling advances the non-terminal version', async () => {
    const cancellation = deferred<Response>()
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockReturnValueOnce(cancellation.promise)
    const { rerender } = render(
      <RunCancellationControl run={run} onRefresh={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: '실행 취소 요청' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    rerender(
      <RunCancellationControl
        run={{ ...run, state_version: 4, state: 'live_preflight_running' }}
        onRefresh={vi.fn()}
      />,
    )

    const button = screen.getByRole('button', { name: '취소 요청 중…' })
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(fetch).toHaveBeenCalledTimes(2)

    cancellation.resolve(response({
      migration_run_uuid: 'run-1',
      state: 'sandbox_running',
      state_version: 4,
      cancellation_requested: true,
      reused: false,
    }, true, 202))
  })

  it('does not replay an ambiguous cancellation and offers status refresh only', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(response({ detail: 'dsn=postgres://secret' }, false, 503))
    const onRefresh = vi.fn()

    render(<RunCancellationControl run={run} onRefresh={onRefresh} />)
    fireEvent.click(screen.getByRole('button', { name: '실행 취소 요청' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('취소 요청 결과를 확인하지 못했습니다')
    expect(alert).not.toHaveTextContent(/503|secret|cancelMigrationRun/)
    expect(screen.queryByRole('button', { name: '실행 취소 요청' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '실행 상태 새로고침' }))

    expect(onRefresh).toHaveBeenCalledOnce()
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it.each([
    [{ ...run, state: 'passed' as const }, 'terminal run'],
    [{ ...run, cancellation_requested: true }, 'existing intent'],
  ])('renders no mutation for %s', (candidate) => {
    const { container } = render(
      <RunCancellationControl run={candidate} onRefresh={vi.fn()} />,
    )

    expect(container).toBeEmptyDOMElement()
    expect(fetch).not.toHaveBeenCalled()
  })
})
