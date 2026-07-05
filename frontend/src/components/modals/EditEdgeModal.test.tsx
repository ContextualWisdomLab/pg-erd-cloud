import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { EditEdgeModal } from './EditEdgeModal';

const edge = { id: 'e1', source: 'users', target: 'orders' };

const baseProps = {
  editingEdge: edge,
  relLabel: 'fk_users_orders',
  setRelLabel: vi.fn(),
  onRelDelete: vi.fn(),
  onRelCancel: vi.fn(),
  onRelSubmit: vi.fn(),
};

afterEach(() => cleanup());

describe('EditEdgeModal', () => {
  it('renders nothing when there is no editing edge', () => {
    render(<EditEdgeModal {...baseProps} editingEdge={null} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders an accessible dialog with the relation source/target', () => {
    render(<EditEdgeModal {...baseProps} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'edit-rel-title');
    expect(screen.getByText('관계 설정')).toBeInTheDocument();
    expect(screen.getByText(/users/)).toBeInTheDocument();
    expect(screen.getByText(/orders/)).toBeInTheDocument();
    expect(screen.getByLabelText('제약조건 이름 (Label)')).toHaveValue('fk_users_orders');
  });

  it('wires delete, cancel and submit buttons to their handlers', () => {
    const onRelDelete = vi.fn();
    const onRelCancel = vi.fn();
    const onRelSubmit = vi.fn();
    render(
      <EditEdgeModal
        {...baseProps}
        onRelDelete={onRelDelete}
        onRelCancel={onRelCancel}
        onRelSubmit={onRelSubmit}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '삭제' }));
    fireEvent.click(screen.getByRole('button', { name: '취소' }));
    fireEvent.click(screen.getByRole('button', { name: '저장' }));
    expect(onRelDelete).toHaveBeenCalledOnce();
    expect(onRelCancel).toHaveBeenCalledOnce();
    expect(onRelSubmit).toHaveBeenCalledOnce();
  });

  it('reports label edits through setRelLabel', () => {
    const setRelLabel = vi.fn();
    render(<EditEdgeModal {...baseProps} setRelLabel={setRelLabel} />);
    fireEvent.change(screen.getByLabelText('제약조건 이름 (Label)'), {
      target: { value: 'fk_new' },
    });
    expect(setRelLabel).toHaveBeenCalledWith('fk_new');
  });
});
