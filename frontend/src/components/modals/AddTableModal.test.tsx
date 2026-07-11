import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { cleanup } from '@testing-library/react';
import { AddTableModal } from './AddTableModal';
import { vi } from 'vitest';

afterEach(() => { cleanup(); });

describe('AddTableModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <AddTableModal
        isOpen={false}
        newTableName=""
        setNewTableName={vi.fn()}
        onAddTableCancel={vi.fn()}
        onAddTableSubmit={vi.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders correctly and calls callbacks', () => {
    const setNewTableName = vi.fn();
    const onAddTableCancel = vi.fn();
    const onAddTableSubmit = vi.fn();

    render(
      <AddTableModal
        isOpen={true}
        newTableName="test_table"
        setNewTableName={setNewTableName}
        onAddTableCancel={onAddTableCancel}
        onAddTableSubmit={onAddTableSubmit}
      />
    );

    expect(screen.getByText('테이블 추가')).toBeInTheDocument();

    const input = screen.getByLabelText('테이블 이름');
    fireEvent.change(input, { target: { value: 'new_val' } });
    expect(setNewTableName).toHaveBeenCalledWith('new_val');

    const submitBtn = screen.getByRole('button', { name: '저장' });
    fireEvent.click(submitBtn);
    expect(onAddTableSubmit).toHaveBeenCalled();

    const cancelBtn = screen.getByRole('button', { name: '취소' });
    fireEvent.click(cancelBtn);
    expect(onAddTableCancel).toHaveBeenCalled();
  });

  it('prevents submission when table name is empty', () => {
    const onAddTableSubmit = vi.fn();
    render(
      <AddTableModal
        isOpen={true}
        newTableName="   "
        setNewTableName={vi.fn()}
        onAddTableCancel={vi.fn()}
        onAddTableSubmit={onAddTableSubmit}
      />
    );
    const form = screen.getByRole('dialog');
    fireEvent.submit(form);
    expect(onAddTableSubmit).not.toHaveBeenCalled();
  });
});
