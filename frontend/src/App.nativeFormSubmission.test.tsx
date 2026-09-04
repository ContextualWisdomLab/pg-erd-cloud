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

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

import App from './App'

beforeEach(() => {
  vi.clearAllMocks()
  api.getMe.mockResolvedValue({ subject: 'test-user', display_name: 'Test User' })
  api.listProjects.mockResolvedValue([
    { project_space_uuid: 'project-1', project_name: 'Billing' },
  ])
  api.listConnections.mockResolvedValue([
    { db_connection_uuid: 'connection-1', conn_name: 'Warehouse' },
  ])
  api.listSnapshots.mockResolvedValue([])
  api.createProject.mockResolvedValue({
    project_space_uuid: 'project-created',
    project_name: 'Keyboard project',
  })
  api.createConnection.mockResolvedValue({
    db_connection_uuid: 'connection-created',
    conn_name: 'Keyboard DB',
  })
  api.createSnapshot.mockResolvedValue({
    schema_snapshot_uuid: 'snapshot-created',
    status: 'queued',
    schema_filter: 'audit',
  })
  api.getSnapshot.mockResolvedValue({
    schema_snapshot_uuid: 'snapshot-created',
    status: 'succeeded',
    schema_filter: 'audit',
    error_message: null,
    snapshot_json: { relations: [], columns: [], pk_columns: [], fk_edges: [] },
  })
  api.createShareLink.mockResolvedValue({ url: 'http://localhost/share/example' })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('native form keyboard submission', () => {
  it('submits the sidebar create actions with Enter without duplicate activation', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: '대시보드' })

    const projectName = screen.getByLabelText('New project')
    await user.clear(projectName)
    await user.type(projectName, 'Keyboard project{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))
    expect(api.createProject).toHaveBeenCalledWith('Keyboard project')

    await waitFor(() => {
      expect(api.listConnections).toHaveBeenCalledWith('project-created')
    })

    const connectionName = screen.getByLabelText('New connection (DSN)')
    await user.clear(connectionName)
    await user.type(connectionName, 'Keyboard DB')
    const dsn = screen.getByLabelText('Connection DSN')
    await user.clear(dsn)
    await user.type(dsn, 'postgresql://db.example.test/app{Enter}')
    await waitFor(() => expect(api.createConnection).toHaveBeenCalledTimes(1))

    const schemaFilter = screen.getByLabelText('Schema filter (optional)')
    await user.type(schemaFilter, 'audit{Enter}')
    await waitFor(() => expect(api.createSnapshot).toHaveBeenCalledTimes(1))
  })

  it('submits the projects-page inline create form with Enter', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: '대시보드' })

    await user.click(screen.getByRole('button', { name: '프로젝트' }))
    const projectName = await screen.findByLabelText('새 프로젝트 이름')
    await user.clear(projectName)
    await user.type(projectName, 'Keyboard project{Enter}')

    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))
    expect(api.createProject).toHaveBeenCalledWith('Keyboard project')
  })
})
