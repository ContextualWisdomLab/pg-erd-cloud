import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ForwardEngineeringModal } from './index'

function response(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

const plan = {
  migration_plan_uuid: 'plan-modal',
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

const run = {
  migration_run_uuid: 'run-modal',
  project_space_uuid: 'project-1',
  migration_plan_uuid: 'plan-modal',
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

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(plan)))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ForwardEngineeringModal', () => {
  it('does not render while closed', () => {
    render(
      <ForwardEngineeringModal
        isOpen={false}
        planId="plan-modal"
        onClose={vi.fn()}
      />,
    )

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('opens a dedicated labelled dialog containing the exact plan review', async () => {
    render(
      <ForwardEngineeringModal
        isOpen
        planId="plan-modal"
        onClose={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: 'Forward Engineering' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(await screen.findByText('plan-modal')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '격리 dry-run 요청' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /apply|적용/i })).not.toBeInTheDocument()
  })

  it('shows an exact read-only run audit surface when a run identity is supplied', async () => {
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input)
      return Promise.resolve(response(url.includes('/migration-runs/') ? run : plan))
    })

    render(
      <ForwardEngineeringModal
        isOpen
        planId="plan-modal"
        runId="run-modal"
        onClose={vi.fn()}
      />,
    )

    expect(await screen.findByText('run-modal')).toBeInTheDocument()
    expect(screen.getByRole('status', { name: '마이그레이션 실행 상태' })).toHaveTextContent(
      '대기 중',
    )
    expect(screen.getByRole('button', { name: '격리 dry-run 요청' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /apply|적용/i })).not.toBeInTheDocument()
  })

  it('replaces the supplied audit surface when a new dry run is accepted', async () => {
    const createdRun = {
      ...run,
      migration_run_uuid: 'run-created',
      state: 'passed',
      state_version: 4,
      observed_base_digest: 'b'.repeat(64),
      finished_at: '2026-08-12T05:01:00Z',
      updated_at: '2026-08-12T05:01:00Z',
    }
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url === '/api/csrf-token') return Promise.resolve(response({ csrf_token: 'csrf' }))
      if (url.endsWith('/dry-runs') && init?.method === 'POST') {
        return Promise.resolve(response({
          migration_run_uuid: 'run-created',
          state: 'queued',
          state_version: 1,
          cancellation_requested: false,
          reused: false,
        }))
      }
      if (url.endsWith('/migration-runs/run-created')) {
        return Promise.resolve(response(createdRun))
      }
      if (url.endsWith('/migration-runs/run-modal')) return Promise.resolve(response(run))
      return Promise.resolve(response(plan))
    })

    render(
      <ForwardEngineeringModal
        isOpen
        planId="plan-modal"
        runId="run-modal"
        onClose={vi.fn()}
      />,
    )

    await screen.findByText('run-modal')
    fireEvent.click(screen.getByRole('button', { name: '격리 dry-run 요청' }))

    expect(await screen.findByText('run-created')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '비실행 apply 의도 등록' }))
      .toBeDisabled()
    await waitFor(() => expect(screen.queryByText('run-modal')).not.toBeInTheDocument())
    expect(screen.getAllByRole('status', { name: '마이그레이션 실행 상태' }))
      .toHaveLength(1)
  })

  it('preserves exact passed dry-run evidence after creating an apply intent', async () => {
    const passedRun = {
      ...run,
      state: 'passed',
      state_version: 4,
      observed_base_digest: 'b'.repeat(64),
    }
    const applyRun = {
      ...run,
      migration_run_uuid: 'apply-intent-modal',
      run_kind: 'apply',
      state: 'queued',
    }
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url === '/api/csrf-token') return Promise.resolve(response({ csrf_token: 'csrf' }))
      if (url.endsWith('/apply-runs') && init?.method === 'POST') {
        return Promise.resolve(response({
          migration_run_uuid: 'apply-intent-modal',
          state: 'queued',
          state_version: 1,
          cancellation_requested: false,
          reused: false,
        }))
      }
      if (url.endsWith('/migration-runs/run-modal')) return Promise.resolve(response(passedRun))
      if (url.endsWith('/migration-runs/apply-intent-modal')) {
        return Promise.resolve(response(applyRun))
      }
      return Promise.resolve(response(plan))
    })

    render(
      <ForwardEngineeringModal
        isOpen
        planId="plan-modal"
        runId="run-modal"
        onClose={vi.fn()}
      />,
    )

    const input = await screen.findByLabelText('대상 연결 이름 확인')
    fireEvent.change(input, { target: { value: 'production-primary' } })
    fireEvent.click(screen.getByRole('button', { name: '비실행 apply 의도 등록' }))

    expect(
      await screen.findByText(/apply-intent-modal/, {}, { timeout: 3000 }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('대상 연결 이름 확인')).toBeInTheDocument()
    expect(screen.queryByText('apply 의도를 등록할 수 없습니다.'))
      .not.toBeInTheDocument()
  })

  it('retires prior passed evidence when a successor dry run is requested', async () => {
    const passedRun = {
      ...run,
      state: 'passed',
      state_version: 4,
      observed_base_digest: 'b'.repeat(64),
    }
    const successorRun = {
      ...run,
      migration_run_uuid: 'dry-run-successor',
      state: 'queued',
    }
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url === '/api/csrf-token') return Promise.resolve(response({ csrf_token: 'csrf' }))
      if (url.endsWith('/dry-runs') && init?.method === 'POST') {
        return Promise.resolve(response({
          migration_run_uuid: 'dry-run-successor',
          state: 'queued',
          state_version: 1,
          cancellation_requested: false,
          reused: false,
        }))
      }
      if (url.endsWith('/migration-runs/run-modal')) return Promise.resolve(response(passedRun))
      if (url.endsWith('/migration-runs/dry-run-successor')) {
        return Promise.resolve(response(successorRun))
      }
      return Promise.resolve(response(plan))
    })

    render(
      <ForwardEngineeringModal
        isOpen
        planId="plan-modal"
        runId="run-modal"
        onClose={vi.fn()}
      />,
    )

    expect(await screen.findByLabelText('대상 연결 이름 확인')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '격리 dry-run 요청' }))

    expect(await screen.findByText('dry-run-successor')).toBeInTheDocument()
    expect(screen.queryByLabelText('대상 연결 이름 확인')).not.toBeInTheDocument()
  })

  it('restores the supplied run when the same modal is closed and reopened', async () => {
    const createdRun = {
      ...run,
      migration_run_uuid: 'run-created',
      state: 'passed',
      state_version: 4,
      observed_base_digest: 'b'.repeat(64),
      finished_at: '2026-08-12T05:01:00Z',
      updated_at: '2026-08-12T05:01:00Z',
    }
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url === '/api/csrf-token') return Promise.resolve(response({ csrf_token: 'csrf' }))
      if (url.endsWith('/dry-runs') && init?.method === 'POST') {
        return Promise.resolve(response({
          migration_run_uuid: 'run-created',
          state: 'queued',
          state_version: 1,
          cancellation_requested: false,
          reused: false,
        }))
      }
      if (url.endsWith('/migration-runs/run-created')) {
        return Promise.resolve(response(createdRun))
      }
      if (url.endsWith('/migration-runs/run-modal')) return Promise.resolve(response(run))
      return Promise.resolve(response(plan))
    })

    const { rerender } = render(
      <ForwardEngineeringModal
        isOpen
        planId="plan-modal"
        runId="run-modal"
        onClose={vi.fn()}
      />,
    )

    await screen.findByText('run-modal')
    fireEvent.click(screen.getByRole('button', { name: '격리 dry-run 요청' }))
    expect(await screen.findByText('run-created')).toBeInTheDocument()

    rerender(
      <ForwardEngineeringModal
        isOpen={false}
        planId="plan-modal"
        runId="run-modal"
        onClose={vi.fn()}
      />,
    )
    rerender(
      <ForwardEngineeringModal
        isOpen
        planId="plan-modal"
        runId="run-modal"
        onClose={vi.fn()}
      />,
    )

    expect(await screen.findByText('run-modal')).toBeInTheDocument()
    expect(screen.queryByText('run-created')).not.toBeInTheDocument()
  })

  it('closes with the explicit button or Escape', () => {
    const onClose = vi.fn()
    const { rerender } = render(
      <ForwardEngineeringModal isOpen planId="plan-modal" onClose={onClose} />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Forward Engineering 닫기' }))
    expect(onClose).toHaveBeenCalledOnce()

    onClose.mockClear()
    rerender(<ForwardEngineeringModal isOpen planId="plan-modal" onClose={onClose} />)
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('moves focus into the dialog and restores it on close', async () => {
    const opener = document.createElement('button')
    opener.textContent = 'Forward 열기'
    document.body.append(opener)
    opener.focus()

    const { rerender } = render(
      <ForwardEngineeringModal isOpen planId="plan-modal" onClose={vi.fn()} />,
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Forward Engineering 닫기' })).toHaveFocus()
    })
    rerender(
      <ForwardEngineeringModal isOpen={false} planId="plan-modal" onClose={vi.fn()} />,
    )
    await waitFor(() => expect(opener).toHaveFocus())
    opener.remove()
  })
})
