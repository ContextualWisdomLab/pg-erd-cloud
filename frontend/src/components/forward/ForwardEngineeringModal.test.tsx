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
    expect(screen.queryByRole('button', { name: /dry|apply|적용|실행/i })).not.toBeInTheDocument()
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
