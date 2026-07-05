import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { AddTableModal } from './AddTableModal';

const baseProps = {
  isOpen: true,
  newTableName: 'users',
  setNewTableName: vi.fn(),
  onAddTableCancel: vi.fn(),
  onAddTableSubmit: vi.fn(),
};

afterEach(() => cleanup());

describe('AddTableModal', () => {
  it('renders nothing when closed', () => {
    render(<AddTableModal {...baseProps} isOpen={false} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders an accessible dialog with the name field', () => {
    render(<AddTableModal {...baseProps} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'add-table-title');
    expect(screen.getByText('테이블 추가')).toBeInTheDocument();
    expect(screen.getByLabelText('테이블 이름')).toHaveValue('users');
  });

  it('disables save while the name is blank and enables it once typed', () => {
    const { rerender } = render(<AddTableModal {...baseProps} newTableName="  " />);
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled();
    rerender(<AddTableModal {...baseProps} newTableName="orders" />);
    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled();
  });

  it('submits a non-empty name and cancels through the handlers', () => {
    const onAddTableSubmit = vi.fn();
    const onAddTableCancel = vi.fn();
    render(
      <AddTableModal
        {...baseProps}
        onAddTableSubmit={onAddTableSubmit}
        onAddTableCancel={onAddTableCancel}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '저장' }));
    expect(onAddTableSubmit).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: '취소' }));
    expect(onAddTableCancel).toHaveBeenCalledOnce();
  });

  it('reports name edits through setNewTableName', () => {
    const setNewTableName = vi.fn();
    render(<AddTableModal {...baseProps} setNewTableName={setNewTableName} />);
    fireEvent.change(screen.getByLabelText('테이블 이름'), {
      target: { value: 'products' },
    });
    expect(setNewTableName).toHaveBeenCalledWith('products');
  });
});
