import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
}));

const layout = vi.hoisted(() => ({
  computeDagreLayout: vi.fn((nodes: Array<{ position: { x: number; y: number } }>) =>
    nodes.map((node) => ({
      ...node,
      position: { x: node.position.x + 200, y: node.position.y + 300 },
    })),
  ),
}));

const initialNodes = [
  {
    id: 'table-1',
    type: 'tableNode',
    position: { x: 5, y: 10 },
    data: {
      title: 'public.users',
      columns: [{ column_name: 'id', data_type: 'bigint', is_not_null: true, is_pk: true }],
      badges: { pk: true, fk: false },
    },
  },
  {
    id: 'table-2',
    type: 'tableNode',
    position: { x: 50, y: 100 },
    data: {
      title: 'public.orders',
      columns: [{ column_name: 'id', data_type: 'bigint', is_not_null: true, is_pk: true }],
      badges: { pk: true, fk: false },
    },
  },
];

vi.mock('./api', () => api);
vi.mock('./erd/dagreLayout', () => layout);
vi.mock('./erd/convert', () => ({
  snapshotToGraph: vi.fn(() => ({ nodes: initialNodes, edges: [] })),
}));
vi.mock('./erd/TableNode', () => ({ default: () => null }));
vi.mock('./components/modals', () => ({
  AddTableModal: () => null,
  CardinalityModal: () => null,
  EditEdgeModal: () => null,
  EditTableModal: () => null,
  ExportModal: () => null,
  GroupModal: () => null,
}));
vi.mock('./erd/export', () => ({
  downloadText: vi.fn(),
  exportDDL: vi.fn(() => ''),
  exportDiagramSvg: vi.fn(() => ''),
  exportDictionaryCsv: vi.fn(() => ''),
  exportDictionaryMarkdown: vi.fn(() => ''),
  exportPlantUml: vi.fn(() => ''),
}));
vi.mock('./erd/mermaid', () => ({ exportMermaid: vi.fn(() => '') }));
vi.mock('./erd/autoInfer', () => ({ inferRelationships: vi.fn(() => []) }));
vi.mock('./erd/dbml', () => ({ exportDbml: vi.fn(() => '') }));
vi.mock('./erd/prisma', () => ({ exportPrisma: vi.fn(() => '') }));

vi.mock('@xyflow/react', async () => {
  const React = await import('react');

  function ReactFlowMock(props: Record<string, any>) {
    React.useEffect(() => {
      props.onInit?.({ fitView: vi.fn() });
    }, [props.onInit]);

    return (
      <div data-testid="react-flow">
        <span data-testid="node-count">{props.nodes.length}</span>
        {props.nodes.map((node: { id: string; position: { x: number; y: number } }) => (
          <span key={node.id} data-testid={`node-position-${node.id}`}>
            {`${node.position.x},${node.position.y}`}
          </span>
        ))}
        {props.children}
      </div>
    );
  }

  return {
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    ReactFlow: ReactFlowMock,
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    addEdge: (next: unknown, current: unknown[]) => [...current, next],
    useNodesState: (initial: unknown[]) => {
      const [nodes, setNodes] = React.useState(initial);
      return [nodes, setNodes, vi.fn()];
    },
    useEdgesState: (initial: unknown[]) => {
      const [edges, setEdges] = React.useState(initial);
      return [edges, setEdges, vi.fn()];
    },
  };
});

import App from './App';

beforeEach(() => {
  vi.clearAllMocks();
  api.getMe.mockResolvedValue({ subject: 'user', display_name: 'User' });
  api.listProjects.mockResolvedValue([{ project_space_uuid: 'project-one', project_name: 'Billing' }]);
  api.listConnections.mockResolvedValue([]);
  api.listSnapshots.mockResolvedValue([
    { schema_snapshot_uuid: 'snapshot-one', status: 'succeeded', schema_filter: 'public' },
  ]);
  api.getSnapshot.mockResolvedValue({
    schema_snapshot_uuid: 'snapshot-one',
    status: 'succeeded',
    schema_filter: 'public',
    error_message: null,
    snapshot_json: { relations: [], columns: [], pk_columns: [], fk_edges: [] },
  });
  api.createShareLink.mockResolvedValue({ url: 'http://localhost/api/share/example' });
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    callback(0);
    return 1;
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('App auto-layout undo', () => {
  it('restores every node to its exact pre-layout coordinates', async () => {
    render(<App />);
    await screen.findByRole('heading', { name: '대시보드' });
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }));
    const openButtons = await screen.findAllByRole('button', { name: '열기' });

    vi.useFakeTimers();
    fireEvent.click(openButtons[0]);
    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByTestId('node-count')).toHaveTextContent('2');

    const originalPositions = new Map(
      initialNodes.map((node) => [
        node.id,
        screen.getByTestId(`node-position-${node.id}`).textContent,
      ]),
    );

    vi.useRealTimers();
    fireEvent.click(screen.getByRole('button', { name: 'ERD 자동 정렬' }));
    await waitFor(() => {
      expect(screen.getByText('정렬 완료', { exact: false })).toBeInTheDocument();
    });

    for (const [nodeId, originalPosition] of originalPositions) {
      expect(screen.getByTestId(`node-position-${nodeId}`)).not.toHaveTextContent(
        originalPosition ?? '',
      );
    }

    fireEvent.click(screen.getByRole('button', { name: '정렬 되돌리기' }));
    expect(screen.getByText('되돌렸습니다', { exact: false })).toBeInTheDocument();

    for (const [nodeId, originalPosition] of originalPositions) {
      expect(screen.getByTestId(`node-position-${nodeId}`)).toHaveTextContent(
        originalPosition ?? '',
      );
    }
  });
});
