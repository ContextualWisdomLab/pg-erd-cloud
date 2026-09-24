import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getMe: vi.fn(),
  listProjects: vi.fn(),
  listConnections: vi.fn(),
  listSnapshots: vi.fn(),
  createProject: vi.fn(),
  createConnection: vi.fn(),
  createSnapshot: vi.fn(),
  getSnapshot: vi.fn(),
  createShareLink: vi.fn(),
}))

vi.mock('./api', () => api)
vi.mock('./components/modals', () => ({
  AddTableModal: () => null,
  CardinalityModal: () => null,
  EditEdgeModal: () => null,
  EditTableModal: () => null,
  ExportModal: () => null,
  GroupModal: () => null,
}))
vi.mock('./erd/TableNode', () => ({ default: () => null }))

vi.mock('@xyflow/react', async () => {
  const React = await import('react')
  return {
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    ReactFlow: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    addEdge: (next: unknown, current: unknown[]) => [...current, next],
    useNodesState: (initial: unknown[]) => {
      const [value, setValue] = React.useState(initial)
      return [value, setValue, vi.fn()]
    },
    useEdgesState: (initial: unknown[]) => {
      const [value, setValue] = React.useState(initial)
      return [value, setValue, vi.fn()]
    },
  }
})

import App from './App'

const projects = [{ project_space_uuid: 'p1', project_name: 'Existing' }]
const connections = [{ db_connection_uuid: 'c1', conn_name: 'Existing DB' }]

beforeEach(() => {
  vi.clearAllMocks()
  api.getMe.mockResolvedValue({ subject: 'user', display_name: 'User', user_account_uuid: 'u' })
  api.listProjects.mockResolvedValue(projects)
  api.listConnections.mockResolvedValue(connections)
  api.listSnapshots.mockResolvedValue([])
  api.createProject.mockResolvedValue({ project_space_uuid: 'p3', project_name: 'New' })
  api.createConnection.mockResolvedValue({ db_connection_uuid: 'c2', conn_name: 'New DB' })
  api.createSnapshot.mockResolvedValue({ schema_snapshot_uuid: 's3', status: 'queued', schema_filter: 'public' })
  api.getSnapshot.mockResolvedValue({
    schema_snapshot_uuid: 's3',
    status: 'queued',
    schema_filter: 'public',
    error_message: null,
    snapshot_json: null,
  })
  api.createShareLink.mockResolvedValue({ url: 'http://localhost/api/share/one' })
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    callback(0)
    return 1
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function openEditor() {
  render(<App />)
  await screen.findByRole('heading', { name: '대시보드' })
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '편집기' }))
  return user
}

describe('creation form keyboard submission', () => {
  it('submits project, connection, and snapshot inputs with Enter exactly once', async () => {
    const user = await openEditor()

    const projectName = screen.getByLabelText('New project')
    await user.clear(projectName)
    await user.type(projectName, 'New{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))
    expect(api.createProject).toHaveBeenLastCalledWith('New')

    const dsn = screen.getByLabelText('Connection DSN')
    await user.type(dsn, 'postgresql://db.example/test{Enter}')
    await waitFor(() => expect(api.createConnection).toHaveBeenCalledTimes(1))
    expect(api.createConnection).toHaveBeenLastCalledWith(
      'p3',
      'target-db',
      'postgresql://db.example/test',
    )

    const schemaFilter = screen.getByLabelText('Schema filter (optional)')
    await user.type(schemaFilter, ' public {Enter}')
    await waitFor(() => expect(api.createSnapshot).toHaveBeenCalledTimes(1))
    expect(api.createSnapshot).toHaveBeenLastCalledWith('p3', 'c2', 'public')
  })

  it('does not start a second project request while the first submit is pending', async () => {
    let resolveProject!: (value: { project_space_uuid: string; project_name: string }) => void
    api.createProject.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveProject = resolve
      }),
    )
    const user = await openEditor()
    const projectName = screen.getByLabelText('New project')
    await user.clear(projectName)
    await user.type(projectName, 'Slow{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))

    await user.keyboard('{Enter}')
    expect(api.createProject).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Creating…' })).toBeDisabled()

    await act(async () => {
      resolveProject({ project_space_uuid: 'p4', project_name: 'Slow' })
    })
  })
})
