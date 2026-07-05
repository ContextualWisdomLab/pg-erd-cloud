import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import type { Node } from '@xyflow/react';

import { CardinalityModal } from './CardinalityModal';
import type { TableNodeData } from '../../erd/convert';

const node = {
  id: 't1',
  type: 'tableNode',
  position: { x: 0, y: 0 },
  data: {
    title: 'users',
    columns: [{ column_name: 'email', data_type: 'text' }],
    badges: { pk: false, fk: false },
  },
} as unknown as Node<TableNodeData>;

const baseProps = {
  isOpen: true,
  cardinalityNode: node,
  nodes: [node],
  cardinalityRowCount: '',
  setCardinalityRowCount: vi.fn(),
  cardinalityRowCountNumber: null,
  cardinalityDistinctCounts: {},
  cardinalityColumnSelections: { email: false },
  cardinalityRecommendations: [],
  appliedCardinalitySignatures: { names: new Set<string>(), columns: new Set<string>() },
  onCloseCardinalityWizard: vi.fn(),
  onCardinalityTableChange: vi.fn(),
  onCardinalityColumnToggle: vi.fn(),
  onCardinalityDistinctCountChange: vi.fn(),
  onApplyCardinalityRecommendation: vi.fn(),
  parsePositiveInteger: (value: string) => {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? n : null;
  },
  calculateCardinalityRatio: () => 0,
  formatPercent: () => '0%',
  strengthLabel: () => '—',
};

afterEach(() => cleanup());

describe('CardinalityModal', () => {
  it('renders nothing when closed or without a target node', () => {
    const { rerender } = render(<CardinalityModal {...baseProps} isOpen={false} />);
    expect(screen.queryByRole('dialog')).toBeNull();
    rerender(<CardinalityModal {...baseProps} cardinalityNode={null} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders an accessible wizard with the column row', () => {
    render(<CardinalityModal {...baseProps} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'cardinality-title');
    expect(screen.getByText('인덱스 카디널리티')).toBeInTheDocument();
    expect(screen.getByLabelText('테이블')).toBeInTheDocument();
    expect(screen.getByLabelText('email 사용')).toBeInTheDocument();
  });

  it('closes through the handler', () => {
    const onCloseCardinalityWizard = vi.fn();
    render(<CardinalityModal {...baseProps} onCloseCardinalityWizard={onCloseCardinalityWizard} />);
    fireEvent.click(screen.getByRole('button', { name: '카디널리티 계산 닫기' }));
    expect(onCloseCardinalityWizard).toHaveBeenCalledOnce();
  });

  it('toggles a column selection through the handler', () => {
    const onCardinalityColumnToggle = vi.fn();
    render(<CardinalityModal {...baseProps} onCardinalityColumnToggle={onCardinalityColumnToggle} />);
    fireEvent.click(screen.getByLabelText('email 사용'));
    expect(onCardinalityColumnToggle).toHaveBeenCalledWith('email', true);
  });
});
