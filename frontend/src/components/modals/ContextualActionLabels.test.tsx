import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { EditEdgeModal } from './EditEdgeModal';
import { EditTableModal } from './EditTableModal';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('contextual modal action labels', () => {
  it.each(['', '   '])(
    'falls back to the relationship id when the label is %j',
    (relLabel) => {
      render(
        <EditEdgeModal
          editingEdge={{ id: 'edge-1', source: 'source-1', target: 'target-1' } as never}
          relLabel={relLabel}
          setRelLabel={vi.fn()}
          onRelDelete={vi.fn()}
          onRelCancel={vi.fn()}
          onRelSubmit={vi.fn()}
        />,
      );

      expect(
        screen.getByRole('button', { name: 'edge-1 관계 삭제' }),
      ).toBeInTheDocument();
    },
  );

  it.each(['', '   '])(
    'falls back to the table id when the title is %j',
    (title) => {
      render(
        <EditTableModal
          isOpen
          editingNode={{
            id: 'table-1',
            type: 'tableNode',
            position: { x: 0, y: 0 },
            data: { title, comment: '', columns: [] },
          } as never}
          setEditingNode={vi.fn()}
          setNodes={vi.fn()}
          onEditTableCancel={vi.fn()}
          onEditTableSubmit={vi.fn()}
          onDeleteTable={vi.fn()}
        />,
      );

      expect(
        screen.getByRole('button', { name: 'table-1 테이블 삭제' }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'table-1 테이블 복제' }),
      ).toBeInTheDocument();
    },
  );
});
