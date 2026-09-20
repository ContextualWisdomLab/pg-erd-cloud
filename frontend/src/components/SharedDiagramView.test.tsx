import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  getSharedLinkInfo: vi.fn(),
  getSharedSnapshot: vi.fn(),
}));

vi.mock('../api', () => api);

vi.mock('@xyflow/react', async () => {
  const React = await import('react');
  return {
    Background: () => <span />,
    Controls: (props: Record<string, unknown>) => (
      <span
        data-testid="shared-controls"
        data-show-interactive={String(props.showInteractive)}
      />
    ),
    MiniMap: () => <span />,
    Handle: () => <span />,
    Position: { Top: 'top', Left: 'left', Right: 'right', Bottom: 'bottom' },
    ReactFlow: (props: Record<string, unknown>) => (
      <div
        data-testid="shared-flow"
        data-draggable={String(props.nodesDraggable)}
        data-connectable={String(props.nodesConnectable)}
        data-selectable={String(props.elementsSelectable)}
        data-nodes-focusable={String(props.nodesFocusable)}
        data-edges-focusable={String(props.edgesFocusable)}
        data-controls-label={String((props.ariaLabelConfig as Record<string, unknown> | undefined)?.['controls.ariaLabel'])}
        data-color-mode={String(props.colorMode)}
      >
        {Array.isArray(props.nodes) ? props.nodes.length : 0} tables
        {props.children as React.ReactNode}
      </div>
    ),
  };
});

import { SharedDiagramView } from './SharedDiagramView';

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

const emptySnapshotJson = {
  relations: [],
  columns: [],
  pk_columns: [],
  fk_edges: [],
};

function snapshotDetail(id: string, schemaFilter: string | null = 'public') {
  return {
    schema_snapshot_uuid: id,
    status: 'succeeded',
    schema_filter: schemaFilter,
    error_message: null,
    snapshot_json: emptySnapshotJson,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('SharedDiagramView', () => {
  it('loads the latest public snapshot into a read-only diagram', async () => {
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-1',
          status: 'succeeded',
          schema_filter: null,
          created_at: '2026-08-09T00:00:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockResolvedValue({
      schema_snapshot_uuid: 'snapshot-1',
      status: 'succeeded',
      schema_filter: null,
      error_message: null,
      snapshot_json: {
        relations: [
          { relation_oid: 1, relation_kind: 'r', schema_name: 'public', relation_name: 'users' },
        ],
        columns: [],
        pk_columns: [],
        fk_edges: [],
      },
    });

    render(<SharedDiagramView shareLinkId="share-1" />);

    expect(await screen.findByRole('heading', { name: '공유 ERD' })).toBeInTheDocument();
    await waitFor(() => expect(api.getSharedSnapshot).toHaveBeenCalledWith('share-1', 'snapshot-1'));
    expect(await screen.findByTestId('shared-flow')).toHaveTextContent('1 tables');
    expect(screen.getByTestId('shared-flow')).toHaveAttribute('data-draggable', 'false');
    expect(screen.getByTestId('shared-flow')).toHaveAttribute('data-connectable', 'false');
    expect(screen.getByTestId('shared-flow')).toHaveAttribute('data-selectable', 'false');
    expect(screen.getByTestId('shared-flow')).toHaveAttribute('data-nodes-focusable', 'false');
    expect(screen.getByTestId('shared-flow')).toHaveAttribute('data-edges-focusable', 'false');
    expect(screen.getByTestId('shared-flow')).toHaveAttribute('data-controls-label', '다이어그램 보기 조작');
    expect(screen.getByTestId('shared-flow')).toHaveAttribute('data-color-mode', 'system');
    expect(screen.getByTestId('shared-controls')).toHaveAttribute(
      'data-show-interactive',
      'false',
    );
    expect(screen.getByRole('option')).toHaveTextContent('전체 스키마 · 2026-08-09 00:00 · succeeded');
    expect(screen.getByText('전체')).toBeInTheDocument();
    expect(screen.getByText('읽기 전용')).toBeInTheDocument();
  });

  it('distinguishes successful versions of the same schema by creation time', async () => {
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-new',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '2026-08-09T10:30:00Z',
        },
        {
          schema_snapshot_uuid: 'snapshot-old',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '2026-08-08T09:15:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockResolvedValue(snapshotDetail('snapshot-new'));

    render(<SharedDiagramView shareLinkId="share-1" />);

    const options = await screen.findAllByRole('option');
    expect(options[0]).toHaveTextContent('public · 2026-08-09 10:30 · succeeded');
    expect(options[1]).toHaveTextContent('public · 2026-08-08 09:15 · succeeded');
  });

  it('adds a short id when schema and creation time are identical', async () => {
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: '11111111-aaaa-bbbb-cccc-dddddddddddd',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '2026-08-09T10:30:00Z',
        },
        {
          schema_snapshot_uuid: '22222222-aaaa-bbbb-cccc-dddddddddddd',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '2026-08-09T10:30:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockResolvedValue(
      snapshotDetail('11111111-aaaa-bbbb-cccc-dddddddddddd'),
    );

    render(<SharedDiagramView shareLinkId="share-1" />);

    const options = await screen.findAllByRole('option');
    expect(options[0]).toHaveTextContent(
      'public · 2026-08-09 10:30 · 11111111 · succeeded',
    );
    expect(options[1]).toHaveTextContent(
      'public · 2026-08-09 10:30 · 22222222 · succeeded',
    );
  });

  it('shows a bounded public-link error without exposing diagnostics', async () => {
    api.getSharedLinkInfo.mockRejectedValue(new Error('backend exploded'));

    render(<SharedDiagramView shareLinkId="share-1" />);

    expect(await screen.findByRole('alert')).toHaveTextContent('공유 링크를 열 수 없습니다');
    expect(screen.getByRole('alert')).not.toHaveTextContent('backend exploded');
  });

  it('shows an empty state when a public link has no snapshots', async () => {
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-empty',
      permission_kind: 'viewer',
      snapshots: [],
    });

    render(<SharedDiagramView shareLinkId="share-empty" />);

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('공유된 스냅샷이 없습니다'),
    );
    expect(api.getSharedSnapshot).not.toHaveBeenCalled();
    expect(screen.queryByRole('combobox', { name: '공유 스냅샷' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('shared-flow')).not.toBeInTheDocument();
  });

  it('distinguishes a missing snapshot payload from an empty schema', async () => {
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-without-data',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '2026-08-09T00:00:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockResolvedValue({
      ...snapshotDetail('snapshot-without-data'),
      snapshot_json: null,
    });

    render(<SharedDiagramView shareLinkId="share-1" />);

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        '공유 스냅샷 데이터가 없습니다',
      ),
    );
    expect(screen.queryByTestId('shared-flow')).not.toBeInTheDocument();
  });

  it('does not request failed or pending snapshots when no successful snapshot exists', async () => {
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-failed',
          status: 'failed',
          schema_filter: null,
          created_at: '2026-08-08T00:00:00Z',
        },
        {
          schema_snapshot_uuid: 'snapshot-pending',
          status: 'pending',
          schema_filter: 'audit',
          created_at: '2026-08-09T00:00:00Z',
        },
      ],
    });
    render(<SharedDiagramView shareLinkId="share-1" />);

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('공유된 스냅샷이 없습니다'),
    );
    expect(api.getSharedSnapshot).not.toHaveBeenCalled();
    expect(screen.queryByRole('combobox', { name: '공유 스냅샷' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('shared-flow')).not.toBeInTheDocument();
  });

  it('loads a newly selected snapshot', async () => {
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-1',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '2026-08-08T00:00:00Z',
        },
        {
          schema_snapshot_uuid: 'snapshot-2',
          status: 'succeeded',
          schema_filter: 'audit',
          created_at: '2026-08-09T00:00:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockImplementation(
      (_shareLinkId: string, snapshotId: string) => Promise.resolve(snapshotDetail(snapshotId, snapshotId === 'snapshot-1' ? 'public' : 'audit')),
    );

    render(<SharedDiagramView shareLinkId="share-1" />);

    const selector = await screen.findByRole('combobox', { name: '공유 스냅샷' });
    await screen.findByText('public');
    fireEvent.change(selector, { target: { value: 'snapshot-2' } });

    expect(await screen.findByText('audit')).toBeInTheDocument();
    expect(api.getSharedSnapshot).toHaveBeenLastCalledWith('share-1', 'snapshot-2');
    expect(selector).toHaveValue('snapshot-2');
  });

  it('clears the previous summary while a newly selected snapshot loads', async () => {
    const pendingSnapshot = deferred<ReturnType<typeof snapshotDetail>>();
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-1',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '2026-08-08T00:00:00Z',
        },
        {
          schema_snapshot_uuid: 'snapshot-2',
          status: 'succeeded',
          schema_filter: 'audit',
          created_at: '2026-08-09T00:00:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockImplementation(
      (_shareLinkId: string, snapshotId: string) =>
        snapshotId === 'snapshot-1'
          ? Promise.resolve(snapshotDetail('snapshot-1', 'public'))
          : pendingSnapshot.promise,
    );

    const { container } = render(<SharedDiagramView shareLinkId="share-1" />);
    const selector = await screen.findByRole('combobox', { name: '공유 스냅샷' });
    await waitFor(() => expect(container.querySelector('.sharedDiagram__summary')).not.toBeNull());

    fireEvent.change(selector, { target: { value: 'snapshot-2' } });
    expect(await screen.findByRole('status')).toHaveTextContent(
      '공유 다이어그램을 불러오는 중입니다',
    );
    expect(container.querySelector('.sharedDiagram__summary')).toBeNull();

    await act(async () => {
      pendingSnapshot.resolve(snapshotDetail('snapshot-2', 'audit'));
      await pendingSnapshot.promise;
    });
    expect(await screen.findByText('audit')).toBeInTheDocument();
  });

  it('shows a bounded error when the selected snapshot cannot be loaded', async () => {
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-1',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '2026-08-09T00:00:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockRejectedValue(new Error('database credentials leaked'));

    render(<SharedDiagramView shareLinkId="share-1" />);

    expect(await screen.findByRole('alert')).toHaveTextContent('공유된 다이어그램을 불러오지 못했습니다');
    expect(screen.getByRole('alert')).not.toHaveTextContent('database credentials leaked');
    expect(screen.queryByTestId('shared-flow')).not.toBeInTheDocument();
  });

  it('ignores a stale public-link response after the link changes', async () => {
    const staleLink = deferred<{
      project_space_uuid: string;
      permission_kind: string;
      snapshots: Array<{
        schema_snapshot_uuid: string;
        status: string;
        schema_filter: string | null;
        created_at: string;
      }>;
    }>();
    api.getSharedLinkInfo.mockImplementation((shareLinkId: string) =>
      shareLinkId === 'share-old'
        ? staleLink.promise
        : Promise.resolve({ project_space_uuid: 'project-new', permission_kind: 'viewer', snapshots: [] }),
    );

    const { rerender } = render(<SharedDiagramView shareLinkId="share-old" />);
    rerender(<SharedDiagramView shareLinkId="share-new" />);
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('공유된 스냅샷이 없습니다'),
    );

    await act(async () => {
      staleLink.resolve({
        project_space_uuid: 'project-old',
        permission_kind: 'viewer',
        snapshots: [
          {
            schema_snapshot_uuid: 'snapshot-old',
            status: 'succeeded',
            schema_filter: 'legacy',
            created_at: '2026-08-08T00:00:00Z',
          },
        ],
      });
      await staleLink.promise;
    });

    expect(screen.getByRole('status')).toHaveTextContent('공유된 스냅샷이 없습니다');
    expect(screen.queryByRole('combobox', { name: '공유 스냅샷' })).not.toBeInTheDocument();
  });

  it('ignores a stale public-link error after the link changes', async () => {
    const staleLink = deferred<never>();
    api.getSharedLinkInfo.mockImplementation((shareLinkId: string) =>
      shareLinkId === 'share-old'
        ? staleLink.promise
        : Promise.resolve({ project_space_uuid: 'project-new', permission_kind: 'viewer', snapshots: [] }),
    );

    const { rerender } = render(<SharedDiagramView shareLinkId="share-old" />);
    rerender(<SharedDiagramView shareLinkId="share-new" />);
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('공유된 스냅샷이 없습니다'),
    );

    await act(async () => {
      staleLink.reject(new Error('stale failure'));
      await staleLink.promise.catch(() => undefined);
    });

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('공유된 스냅샷이 없습니다');
  });

  it('leaves a pending detail request behind when the next link is empty', async () => {
    const pendingSnapshot = deferred<ReturnType<typeof snapshotDetail>>();
    api.getSharedLinkInfo.mockImplementation((shareLinkId: string) =>
      shareLinkId === 'share-old'
        ? Promise.resolve({
            project_space_uuid: 'project-old',
            permission_kind: 'viewer',
            snapshots: [
              {
                schema_snapshot_uuid: 'snapshot-old',
                status: 'succeeded',
                schema_filter: 'legacy',
                created_at: '2026-08-08T00:00:00Z',
              },
            ],
          })
        : Promise.resolve({
            project_space_uuid: 'project-new',
            permission_kind: 'viewer',
            snapshots: [],
          }),
    );
    api.getSharedSnapshot.mockReturnValue(pendingSnapshot.promise);

    const { rerender } = render(<SharedDiagramView shareLinkId="share-old" />);
    await waitFor(() =>
      expect(api.getSharedSnapshot).toHaveBeenCalledWith('share-old', 'snapshot-old'),
    );

    rerender(<SharedDiagramView shareLinkId="share-new" />);

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('공유된 스냅샷이 없습니다'),
    );
    expect(api.getSharedSnapshot).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('main', { name: '공유 ERD 캔버스' })).toHaveAttribute(
      'aria-busy',
      'false',
    );
  });

  it('keeps the newly selected snapshot when an older request resolves late', async () => {
    const staleSnapshot = deferred<ReturnType<typeof snapshotDetail>>();
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-old',
          status: 'succeeded',
          schema_filter: 'legacy',
          created_at: '2026-08-08T00:00:00Z',
        },
        {
          schema_snapshot_uuid: 'snapshot-new',
          status: 'succeeded',
          schema_filter: 'current',
          created_at: '2026-08-09T00:00:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockImplementation(
      (_shareLinkId: string, snapshotId: string) =>
        snapshotId === 'snapshot-old'
          ? staleSnapshot.promise
          : Promise.resolve(snapshotDetail('snapshot-new', 'current')),
    );

    render(<SharedDiagramView shareLinkId="share-1" />);
    const selector = await screen.findByRole('combobox', { name: '공유 스냅샷' });
    await waitFor(() => expect(api.getSharedSnapshot).toHaveBeenCalledWith('share-1', 'snapshot-old'));
    fireEvent.change(selector, { target: { value: 'snapshot-new' } });
    expect(await screen.findByText('current')).toBeInTheDocument();

    await act(async () => {
      staleSnapshot.resolve(snapshotDetail('snapshot-old', 'legacy'));
      await staleSnapshot.promise;
    });

    expect(screen.getByText('current')).toBeInTheDocument();
    expect(screen.queryByText('legacy')).not.toBeInTheDocument();
  });

  it('keeps the newly selected snapshot when an older request rejects late', async () => {
    const staleSnapshot = deferred<never>();
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-old',
          status: 'succeeded',
          schema_filter: 'legacy',
          created_at: '2026-08-08T00:00:00Z',
        },
        {
          schema_snapshot_uuid: 'snapshot-new',
          status: 'succeeded',
          schema_filter: 'current',
          created_at: '2026-08-09T00:00:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockImplementation(
      (_shareLinkId: string, snapshotId: string) =>
        snapshotId === 'snapshot-old'
          ? staleSnapshot.promise
          : Promise.resolve(snapshotDetail('snapshot-new', 'current')),
    );

    render(<SharedDiagramView shareLinkId="share-1" />);
    const selector = await screen.findByRole('combobox', { name: '공유 스냅샷' });
    await waitFor(() => expect(api.getSharedSnapshot).toHaveBeenCalledWith('share-1', 'snapshot-old'));
    fireEvent.change(selector, { target: { value: 'snapshot-new' } });
    expect(await screen.findByText('current')).toBeInTheDocument();

    await act(async () => {
      staleSnapshot.reject(new Error('stale failure'));
      await staleSnapshot.promise.catch(() => undefined);
    });

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText('current')).toBeInTheDocument();
  });

  it('does not start a snapshot request when link loading finishes after unmount', async () => {
    const pendingLink = deferred<{
      project_space_uuid: string;
      permission_kind: string;
      snapshots: Array<{
        schema_snapshot_uuid: string;
        status: string;
        schema_filter: string | null;
        created_at: string;
      }>;
    }>();
    api.getSharedLinkInfo.mockReturnValue(pendingLink.promise);

    const { unmount } = render(<SharedDiagramView shareLinkId="share-unmounted" />);
    unmount();

    await act(async () => {
      pendingLink.resolve({
        project_space_uuid: 'project-unmounted',
        permission_kind: 'viewer',
        snapshots: [
          {
            schema_snapshot_uuid: 'snapshot-unmounted',
            status: 'succeeded',
            schema_filter: 'public',
            created_at: '2026-08-09T00:00:00Z',
          },
        ],
      });
      await pendingLink.promise;
    });

    expect(api.getSharedSnapshot).not.toHaveBeenCalled();
  });

  it('absorbs a snapshot failure that arrives after unmount', async () => {
    const pendingSnapshot = deferred<never>();
    api.getSharedLinkInfo.mockResolvedValue({
      project_space_uuid: 'project-1',
      permission_kind: 'viewer',
      snapshots: [
        {
          schema_snapshot_uuid: 'snapshot-1',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '2026-08-09T00:00:00Z',
        },
      ],
    });
    api.getSharedSnapshot.mockReturnValue(pendingSnapshot.promise);

    const { unmount } = render(<SharedDiagramView shareLinkId="share-1" />);
    await waitFor(() =>
      expect(api.getSharedSnapshot).toHaveBeenCalledWith('share-1', 'snapshot-1'),
    );
    unmount();

    await act(async () => {
      pendingSnapshot.reject(new Error('late snapshot failure'));
      await pendingSnapshot.promise.catch(() => undefined);
    });

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
