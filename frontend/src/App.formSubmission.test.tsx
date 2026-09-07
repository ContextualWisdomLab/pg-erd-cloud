import '@testing-library/jest-dom/vitest'
import userEvent from '@testing-library/user-event'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
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

vi.mock('@xyflow/react', async () => {
  const React = await import('react')
  return {
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    Handle: () => null,
    Position: { Top: 'top', Left: 'left', Right: 'right', Bottom: 'bottom' },
    ReactFlow: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
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

const projects = [{ project_space_uuid: 'p1', project_name: 'Existing project' }]

beforeEach(() => {
  vi.clearAllMocks()
  api.getMe.mockResolvedValue({ subject: 'user', display_name: 'User', user_account_uuid: 'u' })
  api.listProjects.mockResolvedValue(projects)
  api.listConnections.mockResolvedValue([])
  api.listSnapshots.mockResolvedValue([])
  api.createProject.mockResolvedValue({ project_space_uuid: 'p2', project_name: 'Keyboard project' })
  api.createConnection.mockResolvedValue({ db_connection_uuid: 'c2', conn_name: 'Keyboard DB' })
  api.createSnapshot.mockResolvedValue({ schema_snapshot_uuid: 's1', status: 'queued', schema_filter: null })
  api.getSnapshot.mockResolvedValue({
    schema_snapshot_uuid: 's1',
    status: 'succeeded',
    schema_filter: null,
    error_message: null,
    snapshot_json: { relations: [], columns: [], pk_columns: [], fk_edges: [] },
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
})

describe('keyboard form submission', () => {
  it('submits editor project and connection forms with Enter exactly once', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: '대시보드' })
    await user.click(screen.getByRole('button', { name: '편집기' }))

    const projectName = screen.getByLabelText('New project')
    await user.type(projectName, 'Keyboard project{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledWith('Keyboard project'))
    expect(api.createProject).toHaveBeenCalledTimes(1)

    await user.type(screen.getByLabelText('New connection (DSN)'), 'Keyboard DB')
    await user.type(screen.getByLabelText('Connection DSN'), 'postgresql://db.example/test{Enter}')
    await waitFor(() =>
      expect(api.createConnection).toHaveBeenCalledWith(
        'p2',
        'Keyboard DB',
        'postgresql://db.example/test',
      ),
    )
    expect(api.createConnection).toHaveBeenCalledTimes(1)
  })

  it('submits the project-list inline creation form with Enter exactly once', async () => {
    api.listProjects.mockResolvedValueOnce([])
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: '대시보드' })
    await user.click(screen.getByRole('button', { name: '전체 보기' }))

    await user.type(screen.getByLabelText('새 프로젝트 이름'), 'Keyboard project{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledWith('Keyboard project'))
    expect(api.createProject).toHaveBeenCalledTimes(1)
  })
})
