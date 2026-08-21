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
  publicShareIdFromPath: vi.fn(() => null),
}))

type CapturedNode = {
  id: string
  position: { x: number; y: number }
  data: Record<string, unknown>
}

const flowCapture = vi.hoisted(() => ({
  renders: [] as CapturedNode[][],
  setNodes: undefined as
    | ((update: CapturedNode[] | ((current: CapturedNode[]) => CapturedNode[])) => void)
    | undefined,
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
    ReactFlow: (props: { nodes: CapturedNode[]; children?: React.ReactNode }) => {
      flowCapture.renders.push(props.nodes)
      return (
        <div data-testid="react-flow">
          {props.nodes.map((node) => <span key={node.id}>{String(node.data.title)}</span>)}
          {props.children}
        </div>
      )
    },
    addEdge: (edge: unknown, edges: unknown[]) => [...edges, edge],
    useNodesState: (initial: CapturedNode[]) => {
      const [nodes, setNodes] = React.useState(initial)
      flowCapture.setNodes = setNodes as typeof flowCapture.setNodes
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

function detail(id: string, marker: string, status = 'succeeded') {
  return {
    schema_snapshot_uuid: id,
    status,
    schema_filter: null,
    error_message: null,
    snapshot_json: { marker, relations: [], columns: [], pk_columns: [], fk_edges: [] },
  }
}

async function renderReadyApp() {
  render(<App />)
  await waitFor(() => expect(api.listSnapshots).toHaveBeenCalledWith('project-one'))
}

async function diagramOpenButtons() {
  fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
  return screen.findAllByRole('button', { name: '열기' })
}

async function openSnapshot(index: number) {
  const openButtons = await diagramOpenButtons()
  fireEvent.click(openButtons[index]!)
  await waitFor(() => expect(api.getSnapshot).toHaveBeenCalled())
}

function lastNodeData(nodeId: string): Record<string, unknown> {
  const data = flowCapture.renders.at(-1)?.find((node) => node.id === nodeId)?.data
  if (!data) throw new Error(`No rendered data captured for ${nodeId}`)
  return data
}

describe('App search identity and polling isolation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    flowCapture.renders.length = 0
    flowCapture.setNodes = undefined
    api.getMe.mockResolvedValue({ subject: 'user-one', display_name: 'User One' })
    api.listProjects.mockResolvedValue(projects)
    api.listConnections.mockResolvedValue([])
    api.listSnapshots.mockResolvedValue(snapshots)
    api.createShareLink.mockResolvedValue({ url: 'https://example.test/share' })
  })

  afterEach(() => {
    vi.useRealTimers()
    cleanup()
  })

  it('preserves decorated data identity for normalized-query and position-only updates', async () => {
    api.getSnapshot.mockResolvedValue(detail('snapshot-one', 'first'))
    await renderReadyApp()
    await openSnapshot(0)
    await screen.findByText('public.users')

    const search = screen.getByLabelText('테이블 또는 컬럼 검색')
    fireEvent.change(search, { target: { value: 'users' } })
    await waitFor(() => expect(lastNodeData('users').isHighlighted).toBe(true))
    const firstDecorated = lastNodeData('users')

    fireEvent.change(search, { target: { value: ' users ' } })
    await waitFor(() => expect(search).toHaveValue(' users '))
    expect(lastNodeData('users')).toBe(firstDecorated)

    await act(async () => {
      flowCapture.setNodes?.((current) => current.map((node) => (
        node.id === 'users'
          ? { ...node, position: { x: node.position.x + 25, y: node.position.y } }
          : node
      )))
    })
    expect(lastNodeData('users')).toBe(firstDecorated)

    await act(async () => {
      flowCapture.setNodes?.((current) => current.map((node) => (
        node.id === 'users' ? { ...node, data: { ...node.data } } : node
      )))
    })
    const replacedSourceData = lastNodeData('users')
    expect(replacedSourceData).not.toBe(firstDecorated)

    fireEvent.change(search, { target: { value: 'orders' } })
    await waitFor(() => expect(lastNodeData('orders').isHighlighted).toBe(true))
    expect(lastNodeData('users')).not.toBe(replacedSourceData)
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

  it('does not publish a stale polling rejection after the selected snapshot changes', async () => {
    let rejectFirst!: (reason: Error) => void
    api.getSnapshot.mockImplementation((snapshotId: string) => {
      if (snapshotId === 'snapshot-one') {
        return new Promise((_, reject) => { rejectFirst = reject })
      }
      return Promise.resolve(detail('snapshot-two', 'second'))
    })

    await renderReadyApp()
    await openSnapshot(0)
    await openSnapshot(1)
    await screen.findByText('public.accounts')

    await act(async () => {
      rejectFirst(new Error('stale polling failure with secret detail'))
      await Promise.resolve()
    })

    expect(screen.getByText('public.accounts')).toBeInTheDocument()
    expect(screen.queryByText(/stale polling failure with secret detail/i)).not.toBeInTheDocument()
  })

  it('waits for each non-terminal request before scheduling the next poll', async () => {
    let resolveFirst!: (value: ReturnType<typeof detail>) => void
    let resolveSecond!: (value: ReturnType<typeof detail>) => void
    api.getSnapshot
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))

    await renderReadyApp()
    const openButtons = await diagramOpenButtons()
    vi.useFakeTimers()

    fireEvent.click(openButtons[0]!)
    await act(async () => { await Promise.resolve() })
    expect(api.getSnapshot).toHaveBeenCalledTimes(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(api.getSnapshot).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveFirst(detail('snapshot-one', 'first', 'running'))
      await Promise.resolve()
    })
    await act(async () => { await vi.advanceTimersByTimeAsync(999) })
    expect(api.getSnapshot).toHaveBeenCalledTimes(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(api.getSnapshot).toHaveBeenCalledTimes(2)

    await act(async () => {
      resolveSecond(detail('snapshot-one', 'first'))
      await Promise.resolve()
    })
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(api.getSnapshot).toHaveBeenCalledTimes(2)
  })
})
