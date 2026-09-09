import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getMe: vi.fn(),
  createShareLink: vi.fn(),
  createConnection: vi.fn(),
  createProject: vi.fn(),
  createSnapshot: vi.fn(),
  getSnapshot: vi.fn(),
  listConnections: vi.fn(),
  listProjectMembers: vi.fn(),
  listProjects: vi.fn(),
  listSnapshots: vi.fn(),
  upsertProjectMember: vi.fn(),
}))

vi.mock('./api', () => {
  class ProjectMemberRequestError extends Error {
    readonly status: number

    constructor(_operation: string, status: number) {
      super(`project member request failed: ${status}`)
      this.status = status
    }
  }

  return { ...api, ProjectMemberRequestError }
})

vi.mock('@xyflow/react', async () => {
  const ReactModule = await import('react')
  return {
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    ReactFlow: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    Handle: () => null,
    Position: { Top: 'top', Left: 'left', Right: 'right', Bottom: 'bottom' },
    addEdge: (next: unknown, current: unknown[]) => [...current, next],
    useNodesState: (initial: unknown[]) => {
      const [value, setValue] = ReactModule.useState(initial)
      return [value, setValue, vi.fn()]
    },
    useEdgesState: (initial: unknown[]) => {
      const [value, setValue] = ReactModule.useState(initial)
      return [value, setValue, vi.fn()]
    },
  }
})

vi.mock('./components/modals', () => ({
  AccessManagementModal: (props: any) => (
    <div data-testid="access-modal" data-open={String(props.isOpen)}>
      <span data-testid="access-project">{props.projectName}</span>
      <span data-testid="access-members">{props.members.length}</span>
      <span data-testid="access-loading">{String(props.isLoading)}</span>
      {props.isOpen ? <button type="button" data-testid="access-close" onClick={props.onClose}>close</button> : null}
    </div>
  ),
  AddTableModal: () => null,
  CardinalityModal: () => null,
  EditEdgeModal: () => null,
  EditTableModal: () => null,
  GroupModal: () => null,
  ExportModal: (props: any) => (
    props.isOpen ? (
      <div data-testid="export-modal">
        <button type="button" data-testid="access-open" onClick={props.onOpenAccessManagement}>access</button>
        <button type="button" data-testid="export-close" onClick={props.onCloseExport}>close export</button>
      </div>
    ) : null
  ),
}))

vi.mock('./erd/export', () => ({
  downloadText: vi.fn(),
  exportDDL: vi.fn(() => ''),
  exportDiagramSvg: vi.fn(() => '<svg/>'),
  exportDictionaryCsv: vi.fn(() => ''),
  exportDictionaryMarkdown: vi.fn(() => ''),
  exportPlantUml: vi.fn(() => ''),
}))
vi.mock('./erd/mermaid', () => ({ exportMermaid: vi.fn(() => '') }))
vi.mock('./erd/dbml', () => ({ exportDbml: vi.fn(() => '') }))
vi.mock('./erd/prisma', () => ({ exportPrisma: vi.fn(() => '') }))
vi.mock('./erd/autoInfer', () => ({ inferRelationships: vi.fn(() => []) }))

import App from './App'

const projects = [
  { project_space_uuid: 'p1', project_name: 'Billing' },
  { project_space_uuid: 'p2', project_name: 'HR' },
]

beforeEach(() => {
  vi.clearAllMocks()
  api.getMe.mockResolvedValue({ subject: 'owner', display_name: 'Owner', user_account_uuid: 'u1' })
  api.listProjects.mockResolvedValue(projects)
  api.listConnections.mockResolvedValue([])
  api.listSnapshots.mockResolvedValue([])
  api.createShareLink.mockResolvedValue({ url: '/share/test' })
  api.createConnection.mockResolvedValue({})
  api.createProject.mockResolvedValue({})
  api.createSnapshot.mockResolvedValue({})
  api.getSnapshot.mockResolvedValue(null)
  api.upsertProjectMember.mockResolvedValue({})
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 1 })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

async function openAccessManagement() {
  render(<App />)
  await screen.findByRole('heading', { name: '대시보드' })
  fireEvent.click(screen.getByRole('button', { name: '편집기' }))
  fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
  fireEvent.click(screen.getByTestId('access-open'))
}

describe('project access-management lifecycle', () => {
  it('does not commit project A members after selection moves to project B', async () => {
    let resolveProjectA!: (members: unknown[]) => void
    api.listProjectMembers.mockReturnValueOnce(new Promise((resolve) => { resolveProjectA = resolve }))

    await openAccessManagement()
    expect(api.listProjectMembers).toHaveBeenCalledWith('p1')
    expect(screen.getByTestId('access-project')).toHaveTextContent('Billing')

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    await waitFor(() => expect(screen.getByTestId('access-project')).toHaveTextContent('HR'))

    await act(async () => {
      resolveProjectA([
        { user_account_uuid: 'a1', member_subject: 'project-a-member', project_role: 'viewer' },
      ])
      await Promise.resolve()
    })

    expect(screen.getByTestId('access-modal')).toHaveAttribute('data-open', 'false')
    expect(screen.getByTestId('access-members')).toHaveTextContent('0')
  })

  it('clears loaded authorization state when the access modal closes', async () => {
    api.listProjectMembers.mockResolvedValueOnce([
      { user_account_uuid: 'a1', member_subject: 'project-a-member', project_role: 'viewer' },
    ])

    await openAccessManagement()
    await waitFor(() => expect(screen.getByTestId('access-members')).toHaveTextContent('1'))

    fireEvent.click(screen.getByTestId('access-close'))

    expect(screen.getByTestId('access-modal')).toHaveAttribute('data-open', 'false')
    expect(screen.getByTestId('access-members')).toHaveTextContent('0')
    expect(screen.getByTestId('access-loading')).toHaveTextContent('false')
  })
})
