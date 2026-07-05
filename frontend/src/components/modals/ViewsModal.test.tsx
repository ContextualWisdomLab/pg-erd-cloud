import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ViewsModal } from './ViewsModal';
import type { DiagramView } from '../../types';

const views: DiagramView[] = [
  { diagram_view_uuid: 'v1', name: '전체 개요', created_at: '', updated_at: '' },
  { diagram_view_uuid: 'v2', name: '주문 영역', created_at: '', updated_at: '' },
];

const baseProps = {
  isOpen: true,
  views,
  newViewName: '',
  setNewViewName: vi.fn(),
  isSaving: false,
  error: null,
  canSave: true,
  onSaveCurrent: vi.fn(),
  onLoadView: vi.fn(),
  onDeleteView: vi.fn(),
  onClose: vi.fn(),
};

afterEach(() => {
  cleanup();
});

describe('ViewsModal', () => {
  it('lists saved views and loads one', () => {
    const onLoadView = vi.fn();
    render(<ViewsModal {...baseProps} onLoadView={onLoadView} />);
    expect(screen.getByText('전체 개요')).toBeInTheDocument();
    expect(screen.getByText('주문 영역')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: '불러오기' })[1]);
    expect(onLoadView).toHaveBeenCalledWith('v2');
  });

  it('deletes a view', () => {
    const onDeleteView = vi.fn();
    render(<ViewsModal {...baseProps} onDeleteView={onDeleteView} />);
    fireEvent.click(screen.getByRole('button', { name: '전체 개요 삭제' }));
    expect(onDeleteView).toHaveBeenCalledWith('v1');
  });

  it('saves the current layout when a name is entered', () => {
    const onSaveCurrent = vi.fn();
    render(<ViewsModal {...baseProps} newViewName="새 뷰" onSaveCurrent={onSaveCurrent} />);
    fireEvent.click(screen.getByRole('button', { name: '현재 배치 저장' }));
    expect(onSaveCurrent).toHaveBeenCalledOnce();
  });

  it('disables save when name is empty or nothing to save', () => {
    const { rerender } = render(<ViewsModal {...baseProps} newViewName="" />);
    expect(screen.getByRole('button', { name: '현재 배치 저장' })).toBeDisabled();
    rerender(<ViewsModal {...baseProps} newViewName="x" canSave={false} />);
    expect(screen.getByRole('button', { name: '현재 배치 저장' })).toBeDisabled();
  });

  it('shows an empty-state hint when there are no views', () => {
    render(<ViewsModal {...baseProps} views={[]} />);
    expect(screen.getByText('저장된 뷰가 없습니다.')).toBeInTheDocument();
  });
});
