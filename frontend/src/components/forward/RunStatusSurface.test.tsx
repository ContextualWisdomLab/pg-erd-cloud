import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MigrationRun } from '../../types'
import { RunStatusSurface } from './RunStatusSurface'

const run: MigrationRun = {
  migration_run_uuid: 'run-1',
  project_space_uuid: 'project-1',
  migration_plan_uuid: 'plan-1',
  run_kind: 'dry_run',
  state: 'queued',
  state_version: 1,
  plan_digest: 'a'.repeat(64),
  requested_by_user_uuid: 'user-1',
  cancellation_requested: false,
  observed_base_digest: null,
  evidence: {},
  error_code: null,
  created_at: '2026-08-12T05:00:00Z',
  updated_at: '2026-08-12T05:00:00Z',
  started_at: null,
  finished_at: null,
  events: [],
}

function response(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

beforeEach(() => vi.stubGlobal('fetch', vi.fn()))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('RunStatusSurface', () => {
  it('loads one exact run and renders the integrity-checked status', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(run))

    render(<RunStatusSurface runId="run/../other" />)

    expect(screen.getByRole('status')).toHaveTextContent('실행 상태를 불러오는 중입니다.')
    expect(await screen.findByText('run-1')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/migration-runs/run%2F..%2Fother', {
      credentials: 'include',
    })
  })

  it('shows a fixed error and retries without exposing a raw server response', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: false, status: 500 } as Response)
      .mockResolvedValueOnce(response(run))

    render(<RunStatusSurface runId="run-1" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('실행 상태를 불러오지 못했습니다.')
    expect(screen.queryByText(/500|getMigrationRun/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }))
    expect(await screen.findByText('run-1')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('invalidates the last observed run when a polling request fails', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response(run))
      .mockResolvedValueOnce({ ok: false, status: 503 } as Response)
    const onRunLoaded = vi.fn()

    render(
      <RunStatusSurface
        runId="run-1"
        onRunLoaded={onRunLoaded}
        refreshIntervalMs={5}
      />,
    )

    await waitFor(() => expect(onRunLoaded).toHaveBeenCalledWith(run))
    await screen.findByRole('alert')
    expect(onRunLoaded).toHaveBeenLastCalledWith(null)
  })

  it('ignores a late predecessor response when the run identity changes', async () => {
    const first = deferred<Response>()
    vi.mocked(fetch)
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce(response({ ...run, migration_run_uuid: 'run-2' }))

    const { rerender } = render(<RunStatusSurface runId="run-1" />)
    rerender(<RunStatusSurface runId="run-2" />)

    expect(await screen.findByText('run-2')).toBeInTheDocument()
    first.resolve(response(run))
    await first.promise
    expect(screen.queryByText('run-1')).not.toBeInTheDocument()
  })

  it('does not refetch a terminal run when only the observer identity changes', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response({ ...run, state: 'passed' }))
    const { rerender } = render(
      <RunStatusSurface runId="run-1" onRunLoaded={vi.fn()} />,
    )

    expect(await screen.findByText('run-1')).toBeInTheDocument()
    rerender(<RunStatusSurface runId="run-1" onRunLoaded={vi.fn()} />)
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
  })

  it('polls one request at a time until the run reaches a terminal state', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response(run))
      .mockResolvedValueOnce(response({ ...run, state: 'passed', state_version: 4 }))

    render(<RunStatusSurface runId="run-1" refreshIntervalMs={5} />)

    expect(await screen.findByText('run-1')).toBeInTheDocument()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect(screen.getByRole('status', { name: '마이그레이션 실행 상태' })).toHaveTextContent(
      '격리 검증 및 읽기 전용 사전 점검 통과',
    )

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(fetch).toHaveBeenCalledTimes(2)
  })
})
