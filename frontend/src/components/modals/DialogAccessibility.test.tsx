import '@testing-library/jest-dom/vitest';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AddTableModal } from './AddTableModal';
import { GroupModal } from './GroupModal';
import { useDialogAccessibility } from './useDialogAccessibility';

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
    const saveButton = screen.getByRole('button', { name: '저장' });

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
});
