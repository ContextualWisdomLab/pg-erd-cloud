import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EditTableModal } from './EditTableModal';

describe('EditTableModal', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('gives repeated column controls unique accessible names', () => {
    render(
      <EditTableModal
        isOpen
        editingNode={{
          id: 'table-1',
          type: 'table',
          position: { x: 0, y: 0 },
          data: {
            title: 'test_table',
            comment: '',
            columns: [{ column_name: 'test_col', data_type: 'text', is_pk: true, is_not_null: true }]
          }
        } as any}
        setEditingNode={vi.fn()}
        setNodes={vi.fn()}
        onEditTableCancel={vi.fn()}
        onEditTableSubmit={vi.fn()}
        onDeleteTable={vi.fn()}
      />
    );

    expect(screen.getByRole('textbox', { name: 'test_col 컬럼명' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'test_col 데이터 타입' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'test_col PK 설정' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'test_col NN 설정' })).toBeInTheDocument();
  });
});
