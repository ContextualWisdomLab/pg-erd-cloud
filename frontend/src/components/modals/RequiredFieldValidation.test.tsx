import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { EditEdgeModal } from './EditEdgeModal';
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

  it('keeps group creation reachable and explains a whitespace-only group name', () => {
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
    const submit = screen.getByRole('button', { name: '추가' });
    expect(input).toBeRequired();
    expect(submit).not.toBeDisabled();

    fireEvent.submit(input.closest('form')!);

    expect(onCreateBusinessGroup).not.toHaveBeenCalled();
    expect(input).toHaveProperty('validationMessage', '그룹 이름을 입력하세요.');

    fireEvent.change(input, { target: { value: 'Billing' } });
    expect(setNewGroupName).toHaveBeenCalledWith('Billing');
    expect(input).toHaveProperty('validationMessage', '');
  });
});
