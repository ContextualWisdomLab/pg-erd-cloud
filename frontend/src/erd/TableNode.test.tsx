import { render, screen } from '@testing-library/react';
import TableNode from './TableNode';
import { expect, test, vi } from 'vitest';

vi.mock('@xyflow/react', () => ({
  Handle: () => <div data-testid="handle" />,
  Position: { Top: 'top', Right: 'right', Bottom: 'bottom', Left: 'left' }
}));

test('renders TableNode with correct aria-labels for abbreviations', () => {
  const nodeProps = {
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
  };

  render(<TableNode {...nodeProps} />);

  const pkBadges = screen.getAllByLabelText('Primary Key');
  expect(pkBadges.length).toBeGreaterThan(0);

  const fkBadges = screen.getAllByLabelText('Foreign Key');
  expect(fkBadges.length).toBeGreaterThan(0);

  const nnBadges = screen.getAllByLabelText('Not Null');
  expect(nnBadges.length).toBeGreaterThan(0);
});
