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

  it('exposes truncated metadata to keyboard and assistive technology users', () => {
    const data = {
      title: 'public.users',
      comment: 'Stores application users with long operational notes',
      columns: [
        {
          column_name: 'email',
          data_type: 'varchar',
          is_pk: false,
          is_not_null: true,
          column_comment: 'Primary login address used for notifications',
          example_value: 'alex@example.com',
        },
      ],
      indexes: [
        {
          index_name: 'idx_users_email_unique_long_name',
          columns: ['email', 'tenant_id'],
          access_method: 'btree',
        },
      ],
      badges: { pk: false, fk: false },
      businessGroup: { id: 'g1', name: 'Customer operations', color: '#ff0000' },
    };

    render(
      <ReactFlowProvider>
        <TableNode {...({ data, id: "1", type: "tableNode", isConnectable: true } as any)} />
      </ReactFlowProvider>
    );

    for (const name of [
      'Stores application users with long operational notes',
      'Customer operations',
      'Primary login address used for notifications',
      'e.g. alex@example.com',
      '(email, tenant_id)',
    ]) {
      const item = screen.getByLabelText(name);
      expect(item).toHaveAttribute('title', name);
      expect(item).toHaveAttribute('tabindex', '0');
    }

    const indexName = screen.getByLabelText('idx_users_email_unique_long_name');
    expect(indexName).toHaveAttribute('title', 'Access method: btree');
    expect(indexName).toHaveAttribute('tabindex', '0');

    const [notNullBadge] = screen.getAllByLabelText('필수 입력 (Not Null)');
    expect(notNullBadge).toHaveAttribute('title', 'Not Null');
    expect(notNullBadge).toHaveTextContent('NOT NULL');
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
