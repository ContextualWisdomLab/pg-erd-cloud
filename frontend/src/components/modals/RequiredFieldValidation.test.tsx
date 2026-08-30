import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AddTableModal } from './AddTableModal';
import { EditEdgeModal } from './EditEdgeModal';
import { EditTableModal } from './EditTableModal';
import { GroupModal } from './GroupModal';

describe('required modal field validation', () => {
  it('blocks whitespace-only relationship labels with actionable validation', () => {
    const onRelSubmit = vi.fn();
    const setRelLabel = vi.fn();

    render(
      <EditEdgeModal
        editingEdge={{ id: 'edge-1', source: 'orders', target: 'customers', label: '' }}
        relLabel="   "
        setRelLabel={setRelLabel}
        onRelDelete={vi.fn()}
        onRelCancel={vi.fn()}
        onRelSubmit={onRelSubmit}
      />,
    );

    const input = screen.getByLabelText(/제약조건 이름 \(Label\)/);
    expect(input).toBeRequired();

    fireEvent.submit(input.closest('form')!);

    expect(onRelSubmit).not.toHaveBeenCalled();
    expect(input).toHaveProperty('validationMessage', '제약조건 이름을 입력하세요.');

    fireEvent.change(input, { target: { value: 'fk_orders_customer' } });
    expect(setRelLabel).toHaveBeenCalledWith('fk_orders_customer');
    expect(input).toHaveProperty('validationMessage', '');
  });

  it('explains and blocks whitespace-only group creation', () => {
    const onCreateBusinessGroup = vi.fn();
    const setNewGroupName = vi.fn();

    render(
      <GroupModal
        isOpen
        businessGroups={[]}
        newGroupName="   "
        setNewGroupName={setNewGroupName}
        newGroupColor="#1f77b4"
        setNewGroupColor={vi.fn()}
        nodes={[]}
        onCloseGroupManager={vi.fn()}
        onCreateBusinessGroup={onCreateBusinessGroup}
        onDeleteBusinessGroup={vi.fn()}
        onAssignBusinessGroup={vi.fn()}
      />,
    );

    const input = screen.getByLabelText(/그룹 이름/);
    expect(input).toBeRequired();
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('공백이 아닌 그룹 이름을 입력하세요.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '추가' })).toBeDisabled();

    fireEvent.submit(input.closest('form')!);

    expect(onCreateBusinessGroup).not.toHaveBeenCalled();
    expect(input).toHaveProperty('validationMessage', '그룹 이름을 입력하세요.');

    fireEvent.change(input, { target: { value: 'Billing' } });
    expect(setNewGroupName).toHaveBeenCalledWith('Billing');
    expect(input).toHaveProperty('validationMessage', '');
  });

  it('keeps the add-table required marker decorative and the input semantic', () => {
    render(
      <AddTableModal
        isOpen
        newTableName=""
        setNewTableName={vi.fn()}
        onAddTableCancel={vi.fn()}
        onAddTableSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText(/테이블 이름/)).toBeRequired();
    const indicator = document.querySelector('[data-required-indicator="true"]');
    expect(indicator).toHaveAttribute('aria-hidden', 'true');
  });

  it('marks the table title, column name, and data type as required', () => {
    render(
      <EditTableModal
        isOpen
        editingNode={{
          id: 'table-1',
          type: 'tableNode',
          position: { x: 0, y: 0 },
          data: {
            title: 'public.users',
            comment: '',
            columns: [
              { column_name: 'id', data_type: 'bigint', is_pk: true, is_not_null: true },
            ],
            badges: { pk: true, fk: false },
          },
        }}
        setEditingNode={vi.fn()}
        setNodes={vi.fn()}
        onEditTableCancel={vi.fn()}
        onEditTableSubmit={vi.fn()}
        onDeleteTable={vi.fn()}
      />,
    );

    expect(screen.getByLabelText(/테이블명 \(schema\.table\)/)).toBeRequired();
    expect(screen.getByRole('textbox', { name: 'id 컬럼명' })).toBeRequired();
    expect(screen.getByRole('textbox', { name: 'id 데이터 타입' })).toBeRequired();
  });
});
