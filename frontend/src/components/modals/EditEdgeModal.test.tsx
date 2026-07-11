import '@testing-library/jest-dom/vitest';
import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { EditEdgeModal } from './EditEdgeModal';
import { vi } from 'vitest';
import type { Edge } from '@xyflow/react';

describe('EditEdgeModal', () => {
  const mockEdge: Edge = {
    id: 'edge-1',
    source: 'node-1',
    target: 'node-2',
    label: 'fk_relation',
  };

  it('renders nothing when no editingEdge', () => {
    const { container } = render(
      <EditEdgeModal
        editingEdge={null}
        relLabel=""
        setRelLabel={vi.fn()}
        onRelDelete={vi.fn()}
        onRelCancel={vi.fn()}
        onRelSubmit={vi.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders and interacts correctly', () => {
    const setRelLabel = vi.fn();
    const onRelDelete = vi.fn();
    const onRelCancel = vi.fn();
    const onRelSubmit = vi.fn();

    render(
      <EditEdgeModal
        editingEdge={mockEdge}
        relLabel="new_label"
        setRelLabel={setRelLabel}
        onRelDelete={onRelDelete}
        onRelCancel={onRelCancel}
        onRelSubmit={onRelSubmit}
      />
    );

    expect(screen.getByText('관계 설정')).toBeInTheDocument();

    const input = screen.getByLabelText('제약조건 이름 (Label)');
    fireEvent.change(input, { target: { value: 'changed_label' } });
    expect(setRelLabel).toHaveBeenCalledWith('changed_label');

    const submitBtn = screen.getByRole('button', { name: '저장' });
    fireEvent.click(submitBtn);
    expect(onRelSubmit).toHaveBeenCalled();

    const deleteBtn = screen.getByRole('button', { name: '삭제' });
    fireEvent.click(deleteBtn);
    expect(onRelDelete).toHaveBeenCalled();

    const cancelBtn = screen.getByRole('button', { name: '취소' });
    fireEvent.click(cancelBtn);
    expect(onRelCancel).toHaveBeenCalled();
  });
});
