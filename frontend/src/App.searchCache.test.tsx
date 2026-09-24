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

const search = vi.hoisted(() => ({
  findSearchMatchedNodeIds: vi.fn((nodes: Array<{ id: string; data: { title?: string } }>, query: string) => {
    const normalized = query.trim().toLocaleLowerCase()
    return new Set(
      nodes
        .filter((node) => normalized && node.data.title?.toLocaleLowerCase().includes(normalized))
        .map((node) => node.id),
    )
  }),
}))

type CapturedNode = {
  id: string
  position: { x: number; y: number }
  data: Record<string, unknown>
}

const flow = vi.hoisted(() => ({
  nodes: [] as CapturedNode[],
  setNodes: undefined as
    | ((update: CapturedNode[] | ((current: CapturedNode[]) => CapturedNode[])) => void)
    | undefined,
}))

vi.mock('./api', () => api)
vi.mock('./erd/search', () => ({ findSearchMatchedNodeIds: search.findSearchMatchedNodeIds }))
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
      flow.nodes = props.nodes
      return <div data-testid="react-flow">{props.children}</div>
    },
    addEdge: (edge: unknown, edges: unknown[]) => [...edges, edge],
    useNodesState: (initial: CapturedNode[]) => {
      const [nodes, setNodes] = React.useState(initial)
      flow.setNodes = setNodes as typeof flow.setNodes
      return [nodes, setNodes, vi.fn()]
    },
    useEdgesState: (initial: unknown[]) => {
      const [edges, setEdges] = React.useState(initial)
      return [edges, setEdges, vi.fn()]
    },
  }
})

const graphData = vi.hoisted(() => ({
  users: {
    title: 'public.users',
    columns: [{ column_name: 'id', data_type: 'bigint', is_not_null: true, is_pk: true }],
    badges: { pk: true, fk: false },
  },
  orders: {
    title: 'public.orders',
    columns: [{ column_name: 'user_id', data_type: 'bigint', is_not_null: true, is_pk: false }],
    badges: { pk: false, fk: true },
  },
}))

vi.mock('./erd/convert', () => ({
  snapshotToGraph: vi.fn(() => ({
    nodes: [
      { id: 'users', type: 'tableNode', position: { x: 0, y: 0 }, data: graphData.users },
      { id: 'orders', type: 'tableNode', position: { x: 200, y: 0 }, data: graphData.orders },
    ],
    edges: [],
  })),
}))

import App from './App'

describe('App search recomputation boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    flow.nodes = []
    flow.setNodes = undefined
    api.getMe.mockResolvedValue({ subject: 'user-one', display_name: 'User One' })
    api.listProjects.mockResolvedValue([{ project_space_uuid: 'project-one', project_name: 'Project One' }])
    api.listConnections.mockResolvedValue([])
    api.listSnapshots.mockResolvedValue([
      { schema_snapshot_uuid: 'snapshot-one', status: 'succeeded', schema_filter: null },
    ])
    api.getSnapshot.mockResolvedValue({
      schema_snapshot_uuid: 'snapshot-one',
      status: 'succeeded',
      schema_filter: null,
      error_message: null,
      snapshot_json: { relations: [], columns: [], pk_columns: [], fk_edges: [] },
    })
    api.createShareLink.mockResolvedValue({ url: 'https://example.test/share' })
  })

  afterEach(() => cleanup())

  it('reuses matches for position-only updates and recomputes for search-relevant identity changes', async () => {
    render(<App />)
    await waitFor(() => expect(api.listSnapshots).toHaveBeenCalledWith('project-one'))

    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    fireEvent.click((await screen.findAllByRole('button', { name: '열기' }))[0]!)
    await waitFor(() => expect(api.getSnapshot).toHaveBeenCalledWith('snapshot-one'))
    await waitFor(() => expect(flow.nodes.map((node) => node.id)).toEqual(['users', 'orders']))

    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    const input = await screen.findByLabelText('테이블 또는 컬럼 검색')
    fireEvent.change(input, { target: { value: 'users' } })
    await waitFor(() => expect(search.findSearchMatchedNodeIds).toHaveBeenLastCalledWith(expect.any(Array), 'users'))
    const callsAfterSearch = search.findSearchMatchedNodeIds.mock.calls.length

    await act(async () => {
      flow.setNodes?.((current) => current.map((node) => (
        node.id === 'users'
          ? { ...node, position: { x: node.position.x + 25, y: node.position.y } }
          : node
      )))
    })
    await waitFor(() => expect(flow.nodes.find((node) => node.id === 'users')?.position.x).toBe(25))
    expect(search.findSearchMatchedNodeIds).toHaveBeenCalledTimes(callsAfterSearch)

    await act(async () => {
      flow.setNodes?.((current) => current.map((node) => (
        node.id === 'users'
          ? { ...node, data: { ...node.data, title: 'public.customers' } }
          : node
      )))
    })
    await waitFor(() => expect(search.findSearchMatchedNodeIds).toHaveBeenCalledTimes(callsAfterSearch + 1))

    await act(async () => {
      flow.setNodes?.((current) => [...current].reverse())
    })
    await waitFor(() => expect(search.findSearchMatchedNodeIds).toHaveBeenCalledTimes(callsAfterSearch + 2))
  })
})
