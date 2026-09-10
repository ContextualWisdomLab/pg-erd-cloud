import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getMe: vi.fn(),
  createShareLink: vi.fn(),
  createConnection: vi.fn(),
  createProject: vi.fn(),
  createSnapshot: vi.fn(),
  getSnapshot: vi.fn(),
  listConnections: vi.fn(),
  listProjects: vi.fn(),
  listSnapshots: vi.fn(),
}))

vi.mock('./api', () => api)

vi.mock('@xyflow/react', async () => {
  const React = await import('react')
  return {
    Background: () => null,
    MiniMap: () => null,
    Controls: () => null,
    ReactFlow: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    Handle: () => null,
    Position: { Top: 'top', Left: 'left', Right: 'right', Bottom: 'bottom' },
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

beforeEach(() => {
  vi.clearAllMocks()
  api.getMe.mockResolvedValue({ subject: 'user', display_name: 'User', user_account_uuid: 'u1' })
  api.listProjects.mockResolvedValue([
    { project_space_uuid: 'p1', project_name: '<Billing & Core>' },
  ])
  api.listConnections.mockResolvedValue([])
  api.listSnapshots.mockResolvedValue([])
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('uses the project domain value rather than HTML entities in the button accessible name', async () => {
  render(<App />)
  await screen.findByRole('heading', { name: '대시보드' })

  fireEvent.click(screen.getByRole('button', { name: '전체 보기' }))

  expect(
    screen.getByRole('button', { name: '<Billing & Core> 프로젝트 열기' }),
  ).toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: '&lt;Billing &amp; Core&gt; 프로젝트 열기' }),
  ).not.toBeInTheDocument()
})
