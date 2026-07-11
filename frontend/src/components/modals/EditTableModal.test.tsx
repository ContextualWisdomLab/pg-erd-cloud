import '@testing-library/jest-dom/vitest';
import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { EditTableModal } from './EditTableModal';
import { vi } from 'vitest';
import type { Node } from '@xyflow/react';
import type { TableNodeData } from '../../erd/convert';

describe('EditTableModal', () => {
  const mockNode: Node<TableNodeData> = {
    id: 'node-1',
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title: 'public.users',
      comment: 'User table',
      columns: [
        { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
      ],
      badges: { pk: true, fk: false },
    },
  };

  it('renders nothing when closed or no node', () => {
    const { container } = render(
      <EditTableModal
        isOpen={false}
        editingNode={null}
        setEditingNode={vi.fn()}
        setNodes={vi.fn()}
        onEditTableCancel={vi.fn()}
        onEditTableSubmit={vi.fn()}
        onDeleteTable={vi.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders correctly and handles interactions', () => {
    const setEditingNode = vi.fn();
    const setNodes = vi.fn();
    const onEditTableCancel = vi.fn();
    const onEditTableSubmit = vi.fn();
    const onDeleteTable = vi.fn();

    render(
      <EditTableModal
        isOpen={true}
        editingNode={mockNode}
        setEditingNode={setEditingNode}
        setNodes={setNodes}
        onEditTableCancel={onEditTableCancel}
        onEditTableSubmit={onEditTableSubmit}
        onDeleteTable={onDeleteTable}
      />
    );

    expect(screen.getByText('테이블 편집')).toBeInTheDocument();

    // Add column
    const addColumnBtn = screen.getByRole('button', { name: '컬럼 추가' });
    fireEvent.click(addColumnBtn);
    expect(setNodes).toHaveBeenCalled();
    expect(setEditingNode).toHaveBeenCalled();

    // Delete column
    window.confirm = vi.fn(() => true);
    const deleteColBtn = screen.getAllByRole('button', { name: /컬럼 삭제/ })[0];
    fireEvent.click(deleteColBtn);
    expect(setNodes).toHaveBeenCalled();
    expect(setEditingNode).toHaveBeenCalled();

    // Delete Table
    const deleteTableBtn = screen.getByRole('button', { name: '테이블 삭제' });
    fireEvent.click(deleteTableBtn);
    expect(onDeleteTable).toHaveBeenCalled();

    // Duplicate Table
    const duplicateBtn = screen.getByRole('button', { name: '복제' });
    fireEvent.click(duplicateBtn);
    expect(setNodes).toHaveBeenCalled();
    expect(onEditTableCancel).toHaveBeenCalled();

    // Cancel Table
    const cancelBtn = screen.getAllByRole('button', { name: '취소' })[0];
    fireEvent.click(cancelBtn);
    expect(onEditTableCancel).toHaveBeenCalled();
  });
});
