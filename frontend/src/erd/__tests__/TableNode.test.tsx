import '@testing-library/jest-dom/vitest';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import TableNode from '../TableNode';
import { ReactFlowProvider } from '@xyflow/react';

describe('TableNode', () => {
  it('renders table title and columns', () => {
    const data = {
      title: 'public.users',
      comment: 'Users table',
      columns: [
        { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
        { column_name: 'name', data_type: 'varchar', is_pk: false, is_not_null: false, example_value: 'Alice' },
      ],
      badges: { pk: true, fk: false },
      businessGroup: { id: 'g1', name: 'Core', color: '#ff0000' }
    };

    render(
      <ReactFlowProvider>
         <TableNode {...({ data, id: "1", type: "tableNode", isConnectable: true } as any)} />
      </ReactFlowProvider>
    );

    expect(screen.getByText('public.users')).toBeInTheDocument();
    expect(screen.getByText('Users table')).toBeInTheDocument();
    expect(screen.getByText('id')).toBeInTheDocument();
    expect(screen.getByText('int')).toBeInTheDocument();
    expect(screen.getByText('name')).toBeInTheDocument();
    expect(screen.getByText('varchar')).toBeInTheDocument();
    expect(screen.getByText('e.g. Alice')).toBeInTheDocument();
    expect(screen.getByText('Core')).toBeInTheDocument();
  });

  it('uses a fallback accessible name for blank table titles', () => {
    const data = {
      title: '   ',
      columns: [
        { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
      ],
      badges: { pk: true, fk: false },
    };

    render(
      <ReactFlowProvider>
        <TableNode {...({ data, id: "1", type: "tableNode", isConnectable: true } as any)} />
      </ReactFlowProvider>
    );

    expect(screen.getByRole('region', { name: '이름 없는 테이블' })).toBeInTheDocument();
  });
});
