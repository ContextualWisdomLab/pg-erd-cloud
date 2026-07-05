import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DiffModal } from './DiffModal';
import type { SchemaDiff, Snapshot } from '../../types';

const snapshots: Snapshot[] = [
  { schema_snapshot_uuid: 'base-1111-2222', status: 'succeeded', schema_filter: 'public' },
  { schema_snapshot_uuid: 'base-3333-4444', status: 'succeeded', schema_filter: 'sales' },
];

const changedDiff: SchemaDiff = {
  base_table_count: 3,
  target_table_count: 4,
  tables: {
    added: ['public.order_item'],
    removed: ['public.legacy'],
    changed: [
      {
        table: 'public.member',
        columns: {
          added: ['phone'],
          removed: [],
          changed: [
            {
              column: 'email',
              from: { data_type: 'varchar(100)', is_not_null: false },
              to: { data_type: 'varchar(255)', is_not_null: true },
            },
          ],
        },
        primary_key: { from: ['member_id'], to: ['email'] },
      },
    ],
  },
  foreign_keys: {
    added: [
      {
        name: 'fk_x',
        child_table: 'public.order_item',
        child_columns: ['order_id'],
        parent_table: 'public.orders',
        parent_columns: ['order_id'],
      },
    ],
    removed: [],
  },
  summary: {
    tables_added: 1,
    tables_removed: 1,
    tables_changed: 1,
    columns_added: 1,
    columns_removed: 0,
    columns_changed: 1,
    fks_added: 1,
    fks_removed: 0,
    has_changes: true,
  },
};

const baseProps = {
  isOpen: true,
  targetLabel: 'ERD_public_1',
  baseCandidates: snapshots,
  selectedBaseId: 'base-1111-2222',
  diff: null,
  isLoading: false,
  error: null,
  notFound: false,
  onSelectBase: vi.fn(),
  onClose: vi.fn(),
};

afterEach(() => {
  cleanup();
});

describe('DiffModal', () => {
  it('renders added/removed/changed tables and column changes', () => {
    render(<DiffModal {...baseProps} diff={changedDiff} />);
    expect(screen.getByText('+ public.order_item')).toBeInTheDocument();
    expect(screen.getByText('- public.legacy')).toBeInTheDocument();
    expect(screen.getByText('public.member')).toBeInTheDocument();
    expect(screen.getByText('+ 컬럼 phone')).toBeInTheDocument();
    // type + nullability change rendered
    expect(
      screen.getByText(/email: varchar\(100\) → varchar\(255\) NOT NULL/),
    ).toBeInTheDocument();
    // primary key change rendered
    expect(screen.getByText(/member_id → email/)).toBeInTheDocument();
  });

  it('calls onSelectBase when a base snapshot is chosen', () => {
    const onSelectBase = vi.fn();
    render(<DiffModal {...baseProps} onSelectBase={onSelectBase} />);
    fireEvent.change(screen.getByLabelText('비교 기준 스냅샷'), {
      target: { value: 'base-3333-4444' },
    });
    expect(onSelectBase).toHaveBeenCalledWith('base-3333-4444');
  });

  it('shows a no-changes pill when nothing differs', () => {
    const noChange: SchemaDiff = {
      ...changedDiff,
      tables: { added: [], removed: [], changed: [] },
      foreign_keys: { added: [], removed: [] },
      summary: { ...changedDiff.summary, has_changes: false },
    };
    render(<DiffModal {...baseProps} diff={noChange} />);
    expect(screen.getByText('변경 없음')).toBeInTheDocument();
  });

  it('shows a not-found message when the snapshot is missing or unauthorized', () => {
    render(<DiffModal {...baseProps} notFound diff={null} />);
    expect(
      screen.getByText('스냅샷을 찾을 수 없거나 접근 권한이 없습니다.'),
    ).toBeInTheDocument();
  });
});
