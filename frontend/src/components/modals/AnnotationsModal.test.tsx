import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AnnotationsModal } from './AnnotationsModal';
import type { TableAnnotation } from '../../types';

const annotations: TableAnnotation[] = [
  {
    table_annotation_uuid: 'a1',
    schema_name: 'public',
    relation_name: 'orders',
    body: '핵심 주문 테이블',
    created_at: '',
    updated_at: '',
  },
];

const baseProps = {
  isOpen: true,
  annotations,
  isSaving: false,
  error: null,
  onSave: vi.fn(),
  onDelete: vi.fn(),
  onClose: vi.fn(),
};

afterEach(() => cleanup());

describe('AnnotationsModal', () => {
  it('lists existing annotations', () => {
    render(<AnnotationsModal {...baseProps} />);
    expect(screen.getByText('public.orders')).toBeInTheDocument();
    expect(screen.getByText('핵심 주문 테이블')).toBeInTheDocument();
  });

  it('saves a new annotation with trimmed values', () => {
    const onSave = vi.fn();
    render(<AnnotationsModal {...baseProps} onSave={onSave} />);
    fireEvent.change(screen.getByLabelText('테이블'), { target: { value: ' member ' } });
    fireEvent.change(screen.getByLabelText('주석 내용'), { target: { value: ' 회원 마스터 ' } });
    fireEvent.click(screen.getByRole('button', { name: '저장' }));
    expect(onSave).toHaveBeenCalledWith('public', 'member', '회원 마스터');
  });

  it('disables save until schema, table and body are all present', () => {
    render(<AnnotationsModal {...baseProps} />);
    // body empty -> disabled
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('테이블'), { target: { value: 'member' } });
    fireEvent.change(screen.getByLabelText('주석 내용'), { target: { value: 'note' } });
    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled();
  });

  it('deletes an annotation', () => {
    const onDelete = vi.fn();
    render(<AnnotationsModal {...baseProps} onDelete={onDelete} />);
    fireEvent.click(screen.getByRole('button', { name: 'public.orders 주석 삭제' }));
    expect(onDelete).toHaveBeenCalledWith('a1');
  });

  it('loads an annotation into the form when editing', () => {
    render(<AnnotationsModal {...baseProps} />);
    fireEvent.click(screen.getByRole('button', { name: '편집' }));
    expect(screen.getByLabelText('테이블')).toHaveValue('orders');
    expect(screen.getByLabelText('주석 내용')).toHaveValue('핵심 주문 테이블');
  });

  it('shows an empty-state hint when there are no annotations', () => {
    render(<AnnotationsModal {...baseProps} annotations={[]} />);
    expect(screen.getByText('아직 주석이 없습니다.')).toBeInTheDocument();
  });
});
