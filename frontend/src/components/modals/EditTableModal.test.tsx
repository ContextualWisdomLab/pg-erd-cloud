import { render, screen, fireEvent } from '@testing-library/react';
import { EditTableModal } from './EditTableModal';
import { expect, test, vi } from 'vitest';

test('renders EditTableModal with correct aria-labels for abbreviations', () => {
  const mockNode = {
    id: 'test-node',
    data: {
      title: 'Users',
      columns: [
        { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
        { column_name: 'email', data_type: 'varchar', is_not_null: true }
      ],
      badges: {
        pk: true,
        fk: true
      }
    },
    type: 'tableNode' as const,
    selected: false,
    zIndex: 1,
    isConnectable: true,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
    dragging: false,
    draggable: false,
    selectable: false,
    deletable: false,
    position: { x: 0, y: 0 }
  };

  const setEditingNode = vi.fn();
  const setNodes = vi.fn();
  const onEditTableCancel = vi.fn();
  const onEditTableSubmit = vi.fn();
  const onDeleteTable = vi.fn();

  render(
    <EditTableModal
      isOpen={true}
      editingNode={mockNode as any}
      setEditingNode={setEditingNode}
      setNodes={setNodes}
      onEditTableCancel={onEditTableCancel}
      onEditTableSubmit={onEditTableSubmit}
      onDeleteTable={onDeleteTable}
    />
  );

  const pkBadges = screen.getAllByLabelText('Primary Key');
  expect(pkBadges.length).toBeGreaterThan(0);

  const nnBadges = screen.getAllByLabelText('Not Null');
  expect(nnBadges.length).toBeGreaterThan(0);
});
