import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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

const exportMocks = vi.hoisted(() => ({
  downloadText: vi.fn(),
  exportPrisma: vi.fn(() => 'model users {}'),
}));

vi.mock('./api', () => api);
vi.mock('./erd/TableNode', () => ({ default: () => null }));
vi.mock('./erd/convert', () => ({ snapshotToGraph: vi.fn(() => ({ nodes: [], edges: [] })) }));
vi.mock('./erd/export', () => ({
  downloadText: exportMocks.downloadText,
  exportDDL: vi.fn(() => ''),
  exportDiagramSvg: vi.fn(() => ''),
  exportDictionaryCsv: vi.fn(() => ''),
  exportDictionaryMarkdown: vi.fn(() => ''),
  exportPlantUml: vi.fn(() => ''),
}));
vi.mock('./erd/mermaid', () => ({ exportMermaid: vi.fn(() => '') }));
vi.mock('./erd/dbml', () => ({ exportDbml: vi.fn(() => '') }));
vi.mock('./erd/prisma', () => ({ exportPrisma: exportMocks.exportPrisma }));
vi.mock('./erd/autoInfer', () => ({ inferRelationships: vi.fn(() => []) }));

vi.mock('./components/modals', () => ({
  AddTableModal: () => null,
  CardinalityModal: () => null,
  EditEdgeModal: () => null,
  EditTableModal: () => null,
  GroupModal: () => null,
  ExportModal: (props: { onDownloadPrisma: () => void }) => (
    <button type="button" onClick={props.onDownloadPrisma}>
      Prisma 내보내기 테스트
    </button>
  ),
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

beforeEach(() => {
  vi.clearAllMocks();
  api.getMe.mockResolvedValue({ subject: 'user', display_name: 'User' });
  api.listProjects.mockResolvedValue([]);
  api.listConnections.mockResolvedValue([]);
  api.listSnapshots.mockResolvedValue([]);
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('App Prisma export', () => {
  it('downloads the generated Prisma schema', async () => {
    render(<App />);
    await screen.findByRole('heading', { name: '대시보드' });
    fireEvent.click(screen.getByRole('button', { name: '편집기' }));

    fireEvent.click(await screen.findByRole('button', { name: 'Prisma 내보내기 테스트' }));

    expect(exportMocks.exportPrisma).toHaveBeenCalledWith([], []);
    expect(exportMocks.downloadText).toHaveBeenCalledWith(
      'pg-erd-diagram.prisma',
      'model users {}',
      'text/plain',
    );
  });
});
