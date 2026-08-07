import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

const flowCapture = vi.hoisted(() => ({
  renders: [] as Array<Array<{ id: string; data: Record<string, unknown> }>>,
}))

vi.mock('./api', () => api)
vi.mock('./erd/TableNode', () => ({ default: () => null }))
vi.mock('./erd/export', () => ({
  downloadText: vi.fn(),
  exportDDL: vi.fn(() => ''),
  exportDiagramSvg: vi.fn(() => ''),
  exportDictionaryCsv: vi.fn(() => ''),
  exportDictionaryMarkdown: vi.fn(() => ''),
  exportPlantUml: vi.fn(() => ''),
}))
vi.mock('./erd/mermaid', () => ({ exportMermaid: vi.fn(() => '') }))
vi.mock('./erd/dbml', () => ({ exportDbml: vi.fn(() => '') }))
vi.mock('./erd/prisma', () => ({ exportPrisma: vi.fn(() => '') }))
vi.mock('./erd/autoInfer', () => ({ inferRelationships: vi.fn(() => []) }))
vi.mock('./components/modals', () => ({
  AddTableModal: () => null,
  CardinalityModal: () => null,
  EditEdgeModal: () => null,
  EditTableModal: () => null,
  ExportModal: () => null,
  GroupModal: () => null,
}))

vi.mock('@xyflow/react', async () => {
  const React = await import('react')
  return {
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    ReactFlow: (props: { nodes: Array<{ id: string; data: Record<string, unknown> }>; children?: React.ReactNode }) => {
      flowCapture.renders.push(props.nodes)
      return (
        <div data-testid="react-flow">
          {props.nodes.map((node) => <span key={node.id}>{String(node.data.title)}</span>)}
          {props.children}
        </div>
      )
    },
    addEdge: (edge: unknown, edges: unknown[]) => [...edges, edge],
    useNodesState: (initial: unknown[]) => {
      const [nodes, setNodes] = React.useState(initial)
      return [nodes, setNodes, vi.fn()]
    },
    useEdgesState: (initial: unknown[]) => {
      const [edges, setEdges] = React.useState(initial)
      return [edges, setEdges, vi.fn()]
    },
  }
})

const graphData = vi.hoisted(() => ({
  firstUsers: {
    title: 'public.users',
    columns: [{ column_name: 'id', data_type: 'bigint', is_not_null: true, is_pk: true }],
    badges: { pk: true, fk: false },
  },
  firstOrders: {
    title: 'public.orders',
    columns: [{ column_name: 'user_id', data_type: 'bigint', is_not_null: true, is_pk: false }],
    badges: { pk: false, fk: true },
  },
  secondAccounts: {
    title: 'public.accounts',
    columns: [{ column_name: 'account_id', data_type: 'bigint', is_not_null: true, is_pk: true }],
    badges: { pk: true, fk: false },
  },
}))

vi.mock('./erd/convert', () => ({
  snapshotToGraph: vi.fn((snapshotJson: { marker?: string }) => snapshotJson.marker === 'second'
    ? { nodes: [{ id: 'accounts', type: 'tableNode', position: { x: 0, y: 0 }, data: graphData.secondAccounts }], edges: [] }
    : {
        nodes: [
          { id: 'users', type: 'tableNode', position: { x: 0, y: 0 }, data: graphData.firstUsers },
          { id: 'orders', type: 'tableNode', position: { x: 200, y: 0 }, data: graphData.firstOrders },
        ],
        edges: [],
      }),
}))

import App from './App'

const projects = [{ project_space_uuid: 'project-one', project_name: 'Project One' }]
const snapshots = [
  { schema_snapshot_uuid: 'snapshot-one', status: 'running', schema_filter: null },
  { schema_snapshot_uuid: 'snapshot-two', status: 'succeeded', schema_filter: null },
]

const detail = (id: string, marker: string) => ({
  schema_snapshot_uuid: id,
  status: 'succeeded',
  schema_filter: null,
  error_message: null,
  snapshot_json: { marker, relations: [], columns: [], pk_columns: [], fk_edges: [] },
})

async function renderReadyApp() {
  render(<App />)
  await waitFor(() => expect(api.listSnapshots).toHaveBeenCalledWith('project-one'))
}

async function openSnapshot(index: number) {
  fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
  const openButtons = await screen.findAllByRole('button', { name: '열기' })
  fireEvent.click(openButtons[index]!)
  await waitFor(() => expect(api.getSnapshot).toHaveBeenCalled())
}

describe('App search identity and polling isolation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    flowCapture.renders.length = 0
    api.getMe.mockResolvedValue({ subject: 'user-one', display_name: 'User One' })
    api.listProjects.mockResolvedValue(projects)
    api.listConnections.mockResolvedValue([])
    api.listSnapshots.mockResolvedValue(snapshots)
    api.createShareLink.mockResolvedValue({ url: 'https://example.test/share' })
  })

  afterEach(() => cleanup())

  it('reuses decorated node data for an unchanged normalized search and replaces it when the query changes', async () => {
    api.getSnapshot.mockResolvedValue(detail('snapshot-one', 'first'))
    await renderReadyApp()
    await openSnapshot(0)
    await screen.findByText('public.users')

    const search = screen.getByLabelText('테이블 또는 컬럼 검색')
    fireEvent.change(search, { target: { value: 'users' } })
    await waitFor(() => expect(flowCapture.renders.at(-1)?.find((node) => node.id === 'users')?.data.isHighlighted).toBe(true))
    const firstDecorated = flowCapture.renders.at(-1)!.find((node) => node.id === 'users')!.data

    fireEvent.change(search, { target: { value: ' users ' } })
    await waitFor(() => expect(search).toHaveValue(' users '))
    const sameNormalizedQuery = flowCapture.renders.at(-1)!.find((node) => node.id === 'users')!.data
    expect(sameNormalizedQuery).toBe(firstDecorated)

    fireEvent.change(search, { target: { value: 'orders' } })
    await waitFor(() => expect(flowCapture.renders.at(-1)?.find((node) => node.id === 'orders')?.data.isHighlighted).toBe(true))
    const changedQuery = flowCapture.renders.at(-1)!.find((node) => node.id === 'users')!.data
    expect(changedQuery).not.toBe(firstDecorated)
    expect(graphData.firstUsers).not.toHaveProperty('isHighlighted')
  })

  it('ignores a terminal response from a superseded snapshot request', async () => {
    let resolveFirst!: (value: ReturnType<typeof detail>) => void
    api.getSnapshot.mockImplementation((snapshotId: string) => {
      if (snapshotId === 'snapshot-one') {
        return new Promise((resolve) => { resolveFirst = resolve })
      }
      return Promise.resolve(detail('snapshot-two', 'second'))
    })

    await renderReadyApp()
    await openSnapshot(0)
    await waitFor(() => expect(api.getSnapshot).toHaveBeenCalledWith('snapshot-one'))

    await openSnapshot(1)
    await screen.findByText('public.accounts')
    const refreshCountAfterCurrentTerminal = api.listSnapshots.mock.calls.length

    await act(async () => {
      resolveFirst(detail('snapshot-one', 'first'))
      await Promise.resolve()
    })

    expect(screen.getByText('public.accounts')).toBeInTheDocument()
    expect(screen.queryByText('public.users')).not.toBeInTheDocument()
    expect(api.listSnapshots).toHaveBeenCalledTimes(refreshCountAfterCurrentTerminal)
  })
})
