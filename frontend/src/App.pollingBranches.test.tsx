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

vi.mock('./api', () => api);
vi.mock('./erd/TableNode', () => ({ default: () => null }));
vi.mock('./erd/convert', () => ({ snapshotToGraph: vi.fn(() => ({ nodes: [], edges: [] })) }));
vi.mock('./erd/export', () => ({
  downloadText: vi.fn(),
  exportDDL: vi.fn(() => ''),
  exportDiagramSvg: vi.fn(() => ''),
  exportDictionaryCsv: vi.fn(() => ''),
  exportDictionaryMarkdown: vi.fn(() => ''),
  exportPlantUml: vi.fn(() => ''),
}));
vi.mock('./erd/mermaid', () => ({ exportMermaid: vi.fn(() => '') }));
vi.mock('./erd/dbml', () => ({ exportDbml: vi.fn(() => '') }));
vi.mock('./erd/prisma', () => ({ exportPrisma: vi.fn(() => '') }));
vi.mock('./erd/autoInfer', () => ({ inferRelationships: vi.fn(() => []) }));
vi.mock('./components/modals', () => ({
  AddTableModal: () => null,
  CardinalityModal: () => null,
  EditEdgeModal: () => null,
  EditTableModal: () => null,
  ExportModal: () => null,
  GroupModal: () => null,
}));
vi.mock('@xyflow/react', async () => {
  const React = await import('react');
  return {
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    ReactFlow: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    addEdge: (edge: unknown, edges: unknown[]) => [...edges, edge],
    useNodesState: (initial: unknown[]) => {
      const [value, setValue] = React.useState(initial);
      return [value, setValue, vi.fn()];
    },
    useEdgesState: (initial: unknown[]) => {
      const [value, setValue] = React.useState(initial);
      return [value, setValue, vi.fn()];
    },
  };
});

import App from './App';

const project = { project_space_uuid: 'project-one', project_name: 'Project One' };
const snapshotSummary = {
  schema_snapshot_uuid: 'snapshot-one',
  status: 'running',
  schema_filter: 'public',
};
const terminalSnapshot = {
  schema_snapshot_uuid: 'snapshot-one',
  status: 'succeeded',
  schema_filter: 'public',
  error_message: null,
  snapshot_json: { relations: [], columns: [], pk_columns: [], fk_edges: [] },
};

beforeEach(() => {
  vi.clearAllMocks();
  api.getMe.mockResolvedValue({ subject: 'user', display_name: 'User' });
  api.listProjects.mockResolvedValue([project]);
  api.listConnections.mockResolvedValue([]);
  api.createShareLink.mockResolvedValue({ url: 'https://example.test/share' });
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function openSnapshot() {
  fireEvent.click(screen.getByRole('button', { name: '다이어그램' }));
  fireEvent.click((await screen.findAllByRole('button', { name: '열기' }))[0]!);
  await waitFor(() => expect(api.getSnapshot).toHaveBeenCalledWith('snapshot-one'));
}

describe('snapshot polling cleanup branches', () => {
  it('does not apply a terminal snapshot-list refresh that resolves after unmount', async () => {
    let resolveRefresh!: (value: typeof snapshotSummary[]) => void;
    api.listSnapshots
      .mockResolvedValueOnce([snapshotSummary])
      .mockImplementationOnce(() => new Promise((resolve) => { resolveRefresh = resolve; }));
    api.getSnapshot.mockResolvedValue(terminalSnapshot);

    const view = render(<App />);
    await waitFor(() => expect(api.listSnapshots).toHaveBeenCalledTimes(1));
    await openSnapshot();
    await waitFor(() => expect(api.listSnapshots).toHaveBeenCalledTimes(2));
    view.unmount();

    await act(async () => {
      resolveRefresh([{ ...snapshotSummary, schema_snapshot_uuid: 'stale-snapshot' }]);
      await Promise.resolve();
    });

    expect(api.listSnapshots).toHaveBeenCalledTimes(2);
  });

  it('does not publish a terminal snapshot-list refresh error after unmount', async () => {
    let rejectRefresh!: (reason: Error) => void;
    api.listSnapshots
      .mockResolvedValueOnce([snapshotSummary])
      .mockImplementationOnce(() => new Promise((_, reject) => { rejectRefresh = reject; }));
    api.getSnapshot.mockResolvedValue(terminalSnapshot);

    const view = render(<App />);
    await waitFor(() => expect(api.listSnapshots).toHaveBeenCalledTimes(1));
    await openSnapshot();
    await waitFor(() => expect(api.listSnapshots).toHaveBeenCalledTimes(2));
    view.unmount();

    await act(async () => {
      rejectRefresh(new Error('stale refresh failure'));
      await Promise.resolve();
    });

    expect(api.listSnapshots).toHaveBeenCalledTimes(2);
  });

  it('does not schedule another non-terminal poll after synchronous cleanup', async () => {
    api.listSnapshots.mockResolvedValue([snapshotSummary]);
    let unmountApp = () => {};
    let statusReads = 0;
    api.getSnapshot.mockResolvedValue({
      ...terminalSnapshot,
      get status() {
        statusReads += 1;
        if (statusReads === 1) unmountApp();
        return 'running';
      },
    });

    const view = render(<App />);
    unmountApp = view.unmount;
    await waitFor(() => expect(api.listSnapshots).toHaveBeenCalledTimes(1));
    await openSnapshot();
    await act(async () => { await Promise.resolve(); });

    expect(statusReads).toBeGreaterThan(0);
    expect(api.getSnapshot).toHaveBeenCalledTimes(1);
  });

  it('does not publish a snapshot polling error after unmount', async () => {
    api.listSnapshots.mockResolvedValue([snapshotSummary]);
    let rejectSnapshot!: (reason: Error) => void;
    api.getSnapshot.mockImplementationOnce(
      () => new Promise((_, reject) => { rejectSnapshot = reject; }),
    );

    const view = render(<App />);
    await waitFor(() => expect(api.listSnapshots).toHaveBeenCalledTimes(1));
    await openSnapshot();
    view.unmount();

    await act(async () => {
      rejectSnapshot(new Error('stale polling failure'));
      await Promise.resolve();
    });

    expect(api.getSnapshot).toHaveBeenCalledTimes(1);
  });
});
