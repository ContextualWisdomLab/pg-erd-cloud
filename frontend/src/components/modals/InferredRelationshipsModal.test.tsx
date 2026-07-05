import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { InferredRelationshipsModal } from './InferredRelationshipsModal';
import type { InferredRelationship } from '../../types';

const relationships: InferredRelationship[] = [
  {
    child_schema: 'public', child_table: 'orders', child_column: 'member_id',
    parent_schema: 'public', parent_table: 'member', parent_column: 'member_id',
    confidence: 'high', reason: "column 'member_id' matches table 'member'",
  },
  {
    child_schema: 'public', child_table: 'orders', child_column: 'coupon_id',
    parent_schema: 'public', parent_table: 'coupon', parent_column: 'id',
    confidence: 'medium', reason: "column 'coupon_id' matches table 'coupon' (type differs)",
  },
];

const baseProps = {
  isOpen: true,
  relationships,
  isLoading: false,
  error: null,
  onClose: vi.fn(),
};

afterEach(() => cleanup());

describe('InferredRelationshipsModal', () => {
  it('lists inferred relationships with confidence labels', () => {
    render(<InferredRelationshipsModal {...baseProps} />);
    expect(screen.getByText('orders.member_id → member.member_id')).toBeInTheDocument();
    expect(screen.getByText('높음')).toBeInTheDocument();
    expect(screen.getByText('orders.coupon_id → coupon.id')).toBeInTheDocument();
    expect(screen.getByText('보통')).toBeInTheDocument();
  });

  it('shows a loading status while analyzing', () => {
    render(<InferredRelationshipsModal {...baseProps} isLoading relationships={[]} />);
    expect(screen.getByRole('status')).toHaveTextContent('분석 중');
  });

  it('shows an empty-state hint when nothing is inferred', () => {
    render(<InferredRelationshipsModal {...baseProps} relationships={[]} />);
    expect(screen.getByText('추론된 관계가 없습니다.')).toBeInTheDocument();
  });

  it('renders nothing when closed', () => {
    render(<InferredRelationshipsModal {...baseProps} isOpen={false} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
