import '@testing-library/jest-dom/vitest';
import type { Node } from '@xyflow/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AddTableModal } from './AddTableModal';
import { EditEdgeModal } from './EditEdgeModal';
import { EditTableModal } from './EditTableModal';
import { GroupModal } from './GroupModal';
import { useDialogAccessibility } from './useDialogAccessibility';
import type { TableNodeData } from '../../erd/convert';

afterEach(() => {
  cleanup();
});

describe('modal dialog accessibility', () => {
  it('closes with Escape and restores focus to the opener', async () => {
    const onCloseGroupManager = vi.fn();

    function Harness() {
      const [isOpen, setIsOpen] = useState(false);
      const handleClose = () => {
        onCloseGroupManager();
        setIsOpen(false);
      };

      return (
        <>
          <button
            type="button"
            onClick={(event) => {
              event.currentTarget.focus();
              setIsOpen(true);
            }}
          >
            Open group manager
          </button>
          <GroupModal
            isOpen={isOpen}
            businessGroups={[]}
            newGroupName=""
            setNewGroupName={vi.fn()}
            newGroupColor="#047857"
            setNewGroupColor={vi.fn()}
            nodes={[]}
            onCloseGroupManager={handleClose}
            onCreateBusinessGroup={vi.fn()}
            onDeleteBusinessGroup={vi.fn()}
            onAssignBusinessGroup={vi.fn()}
          />
        </>
      );
    }

    const user = userEvent.setup();
    render(<Harness />);

    const opener = screen.getByRole('button', { name: 'Open group manager' });
    await user.click(opener);

    await waitFor(() => expect(screen.getByLabelText('그룹 이름')).toHaveFocus());
    await user.keyboard('{Escape}');
    expect(onCloseGroupManager).toHaveBeenCalledOnce();

    await waitFor(() => expect(opener).toHaveFocus());
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('traps Tab navigation inside the dialog', async () => {
    render(
      <AddTableModal
        isOpen
        newTableName="users"
        setNewTableName={vi.fn()}
        onAddTableCancel={vi.fn()}
        onAddTableSubmit={vi.fn()}
      />,
    );

    const tableNameInput = screen.getByLabelText('테이블 이름');
    const saveButton = screen.getByRole('button', { name: '새 테이블 저장' });

    await waitFor(() => expect(tableNameInput).toHaveFocus());

    saveButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(tableNameInput).toHaveFocus();

    tableNameInput.focus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(saveButton).toHaveFocus();
  });

  it('keeps aria-hidden=false controls in the focus trap', async () => {
    function TestDialog() {
      const dialogRef = useDialogAccessibility(true, vi.fn());

      return (
        <div ref={dialogRef} role="dialog" aria-modal="true" tabIndex={-1}>
          <button type="button" aria-hidden="false">
            First visible action
          </button>
          <button type="button">Last action</button>
        </div>
      );
    }

    render(<TestDialog />);

    const firstButton = screen.getByRole('button', { name: 'First visible action' });
    const lastButton = screen.getByRole('button', { name: 'Last action' });

    await waitFor(() => expect(firstButton).toHaveFocus());

    lastButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(firstButton).toHaveFocus();
  });

  it('names generic dialog action buttons with contextual labels', () => {
    const editingNode: Node<TableNodeData> = {
      id: 'users',
      type: 'tableNode',
      position: { x: 0, y: 0 },
      data: {
        title: 'public.users',
        comment: null,
        columns: [],
        badges: { pk: false, fk: false },
      },
    };

    render(
      <>
        <AddTableModal
          isOpen
          newTableName="users"
          setNewTableName={vi.fn()}
          onAddTableCancel={vi.fn()}
          onAddTableSubmit={vi.fn()}
        />
        <EditEdgeModal
          editingEdge={{ id: 'fk_users_accounts', source: 'users', target: 'accounts' }}
          relLabel="fk_users_accounts"
          setRelLabel={vi.fn()}
          onRelDelete={vi.fn()}
          onRelCancel={vi.fn()}
          onRelSubmit={vi.fn()}
        />
        <EditTableModal
          isOpen
          editingNode={editingNode}
          setEditingNode={vi.fn()}
          setNodes={vi.fn()}
          onEditTableCancel={vi.fn()}
          onEditTableSubmit={vi.fn()}
          onDeleteTable={vi.fn()}
        />
      </>,
    );

    expect(screen.getByRole('button', { name: '테이블 추가 취소' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '새 테이블 저장' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '관계 삭제' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '관계 설정 취소' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '관계 저장' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'public.users 테이블 삭제' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'public.users 테이블 복제' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'public.users 테이블 편집 취소' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'public.users 테이블 편집 저장' })).toBeInTheDocument();
  });
});
