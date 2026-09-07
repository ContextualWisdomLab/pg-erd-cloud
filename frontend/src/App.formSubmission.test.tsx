import '@testing-library/jest-dom/vitest'
import userEvent from '@testing-library/user-event'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
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

type ProjectResult = { project_space_uuid: string; project_name: string }
type ConnectionResult = { db_connection_uuid: string; conn_name: string }

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => {
    resolve = next
  })
  return { promise, resolve }
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getMe.mockResolvedValue({ subject: 'user', display_name: 'User', user_account_uuid: 'u' })
  api.listProjects.mockResolvedValue(projects)
  api.listConnections.mockResolvedValue([])
  api.listSnapshots.mockResolvedValue([])
  let projectCounter = 2;
  api.createProject.mockImplementation((name) => {
    projectCounter++;
    return Promise.resolve({ project_space_uuid: `p${projectCounter}`, project_name: name });
  });
  let connCounter = 1;
  api.createConnection.mockImplementation((projectId, name, dsn) => {
    connCounter++;
    return Promise.resolve({ db_connection_uuid: `c${connCounter}`, conn_name: name });
  });
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
  it('submits editor project and connection forms with Enter without duplicate requests', async () => {
    const projectRequest = deferred<ProjectResult>()
    const connectionRequest = deferred<ConnectionResult>()
    api.createProject.mockReturnValueOnce(projectRequest.promise)
    api.createConnection.mockReturnValueOnce(connectionRequest.promise)

    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: '대시보드' })
    await user.click(screen.getByRole('button', { name: '편집기' }))

    const projectName = screen.getByLabelText('New project')
    await user.clear(projectName)
    await user.type(projectName, 'Keyboard project{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledWith('Keyboard project'))
    expect(screen.getByRole('button', { name: 'Creating…' })).toBeDisabled()
    await user.keyboard('{Enter}')
    expect(api.createProject).toHaveBeenCalledTimes(1)

    await act(async () => {
      projectRequest.resolve({ project_space_uuid: 'p2', project_name: 'Keyboard project' })
      await projectRequest.promise
    })

    const connName = screen.getByLabelText('New connection (DSN)')
    await user.clear(connName)
    await user.type(connName, 'Keyboard DB')
    const dsn = screen.getByLabelText('Connection DSN')
    await user.clear(dsn)
    await user.type(dsn, 'postgresql://db.example/test{Enter}')
    await waitFor(() =>
      expect(api.createConnection).toHaveBeenCalledWith(
        expect.stringMatching(/^p/),
        'Keyboard DB',
        'postgresql://db.example/test',
      ),
    )
    expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled()
    await user.keyboard('{Enter}')
    expect(api.createConnection).toHaveBeenCalledTimes(1)

    await act(async () => {
      connectionRequest.resolve({ db_connection_uuid: 'c2', conn_name: 'Keyboard DB' })
      await connectionRequest.promise
    })
  })

  it('submits the project-list inline form with Enter without duplicate requests', async () => {
    api.listProjects.mockResolvedValueOnce([])
    const projectRequest = deferred<ProjectResult>()
    api.createProject.mockReturnValueOnce(projectRequest.promise)

    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: '대시보드' })
    await user.click(screen.getByRole('button', { name: '전체 보기' }))

    const projectName = screen.getByLabelText('새 프로젝트 이름')
    await user.clear(projectName)
    await user.type(projectName, 'Keyboard project{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledWith('Keyboard project'))
    expect(screen.getByRole('button', { name: '생성 중' })).toBeDisabled()
    await user.keyboard('{Enter}')
    expect(api.createProject).toHaveBeenCalledTimes(1)

    await act(async () => {
      projectRequest.resolve({ project_space_uuid: 'p2', project_name: 'Keyboard project' })
      await projectRequest.promise
    })
  })
})
