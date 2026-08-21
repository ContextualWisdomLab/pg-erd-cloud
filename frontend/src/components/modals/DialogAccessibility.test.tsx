import '@testing-library/jest-dom/vitest';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AddTableModal } from './AddTableModal';
import { GroupModal } from './GroupModal';
import { ModalShell } from './ModalShell';
import { useDialogAccessibility } from './useDialogAccessibility';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('modal dialog accessibility', () => {
  it('provides one labelled shell with an explicit backdrop policy', async () => {
    const onClose = vi.fn();
    const { container, rerender } = render(
      <ModalShell
        title="테이블 추가"
        titleId="modal-shell-title"
        onClose={onClose}
        closeLabel="테이블 추가 닫기"
        size="addTable"
      >
        <button type="button">본문 작업</button>
      </ModalShell>,
    );

    const dialog = screen.getByRole('dialog', { name: '테이블 추가' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveClass('modalShell--addTable');
    expect(within(dialog).queryByRole('banner')).not.toBeInTheDocument();
    expect(within(dialog).queryByRole('contentinfo')).not.toBeInTheDocument();

    fireEvent.click(container.querySelector('.modalOverlay')!);
    expect(onClose).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: '테이블 추가 닫기' }));
    expect(onClose).toHaveBeenCalledOnce();

    onClose.mockClear();
    rerender(
      <ModalShell
        title="테이블 추가"
        titleId="modal-shell-title"
        onClose={onClose}
        closeLabel="테이블 추가 닫기"
        size="addTable"
        closeOnBackdrop
      >
        <button type="button">본문 작업</button>
      </ModalShell>,
    );
    fireEvent.click(container.querySelector('.modalOverlay')!);
    expect(onClose).toHaveBeenCalledOnce();
  });

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

  it('restores focus to the focusable ancestor of an SVG interaction target', async () => {
    function Harness() {
      const [isOpen, setIsOpen] = useState(false);
      return (
        <>
          <button type="button">이전 포커스</button>
          <svg>
            <g
              role="button"
              tabIndex={0}
              aria-label="관계 편집 열기"
              onClick={() => setIsOpen(true)}
            >
              <path data-testid="svg-opener-target" />
            </g>
          </svg>
          {isOpen ? (
            <ModalShell
              title="관계 편집"
              titleId="focus-return-title"
              onClose={() => setIsOpen(false)}
              closeLabel="관계 편집 닫기"
              size="relationship"
            >
              <button type="button">관계 저장</button>
            </ModalShell>
          ) : null}
        </>
      );
    }

    render(<Harness />);
    const fallback = screen.getByRole('button', { name: '이전 포커스' });
    const opener = screen.getByRole('button', { name: '관계 편집 열기' });
    fallback.focus();
    fallback.blur();

    const svgTarget = screen.getByTestId('svg-opener-target');
    fireEvent.mouseDown(svgTarget);
    fireEvent.click(svgTarget);
    await waitFor(() => expect(screen.getByRole('dialog', { name: '관계 편집' })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: '관계 편집 닫기' }));
    await waitFor(() => expect(opener).toHaveFocus());
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
    expect(screen.getByRole('button', { name: '테이블 추가 닫기' })).toHaveFocus();

    screen.getByRole('button', { name: '테이블 추가 닫기' }).focus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(saveButton).toHaveFocus();
  });

  it('recovers focus when Tab starts outside the open dialog', async () => {
    render(
      <>
        <button type="button">외부 작업</button>
        <AddTableModal
          isOpen
          newTableName="users"
          setNewTableName={vi.fn()}
          onAddTableCancel={vi.fn()}
          onAddTableSubmit={vi.fn()}
        />
      </>,
    );

    const outsideButton = screen.getByRole('button', { name: '외부 작업' });
    const firstDialogControl = screen.getByRole('button', { name: '테이블 추가 닫기' });
    const lastDialogControl = screen.getByRole('button', { name: '저장' });

    await waitFor(() => expect(screen.getByLabelText('테이블 이름')).toHaveFocus());

    outsideButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(firstDialogControl).toHaveFocus();

    outsideButton.focus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(lastDialogControl).toHaveFocus();
  });

  it('ignores non-HTML/SVG elements that expose a tabindex', async () => {
    function ForeignNamespaceDialog() {
      const dialogRef = useDialogAccessibility(true, vi.fn());
      return (
        <div ref={dialogRef} role="dialog" aria-modal="true" tabIndex={-1}>
          <button type="button">유효한 작업</button>
        </div>
      );
    }

    render(<ForeignNamespaceDialog />);
    const dialog = screen.getByRole('dialog');
    const mathElement = document.createElementNS(
      'http://www.w3.org/1998/Math/MathML',
      'math',
    );
    mathElement.setAttribute('tabindex', '0');
    dialog.prepend(mathElement);

    await waitFor(() =>
      expect(screen.getByRole('button', { name: '유효한 작업' })).toHaveFocus(),
    );
  });

  it('treats a closed details summary as the final visible Tab stop', async () => {
    function DetailsDialog() {
      const dialogRef = useDialogAccessibility(true, vi.fn());
      return (
        <div ref={dialogRef} role="dialog" aria-modal="true" tabIndex={-1}>
          <button type="button">첫 작업</button>
          <details>
            <summary>기타 산출물</summary>
            <button type="button">숨겨진 산출물</button>
          </details>
        </div>
      );
    }

    render(<DetailsDialog />);
    const firstButton = screen.getByRole('button', { name: '첫 작업' });
    const summary = screen.getByText('기타 산출물');

    await waitFor(() => expect(firstButton).toHaveFocus());
    summary.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(firstButton).toHaveFocus();
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

  it('excludes controls hidden from assistive technology from the focus trap', async () => {
    function TestDialog() {
      const dialogRef = useDialogAccessibility(true, vi.fn());

      return (
        <div ref={dialogRef} role="dialog" aria-modal="true" tabIndex={-1}>
          <button type="button">First visible action</button>
          <div aria-hidden="true">
            <button type="button">Hidden action</button>
          </div>
          <button type="button">Last visible action</button>
        </div>
      );
    }

    render(<TestDialog />);

    const firstButton = screen.getByRole('button', { name: 'First visible action' });
    const lastButton = screen.getByRole('button', { name: 'Last visible action' });
    await waitFor(() => expect(firstButton).toHaveFocus());

    lastButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(firstButton).toHaveFocus();
  });

  it('does not install dialog behavior while the hook is closed', () => {
    const onClose = vi.fn();

    function ClosedDialog() {
      const dialogRef = useDialogAccessibility(false, onClose);
      return <div ref={dialogRef} role="dialog" tabIndex={-1}>Closed dialog</div>;
    }

    render(<ClosedDialog />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('focuses a buttonless dialog and keeps Tab inside it', async () => {
    function ButtonlessDialog() {
      const dialogRef = useDialogAccessibility(true, vi.fn());
      return <div ref={dialogRef} role="dialog" tabIndex={-1}>No controls</div>;
    }

    render(<ButtonlessDialog />);
    const dialog = screen.getByRole('dialog');
    await waitFor(() => expect(dialog).toHaveFocus());
    fireEvent.keyDown(document, { key: 'x' });
    document.body.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(dialog).toHaveFocus();
  });

  it('safely handles an open hook before its dialog ref is attached', () => {
    vi.useFakeTimers();
    function MissingDialog() {
      useDialogAccessibility(true, vi.fn());
      return <span>no dialog ref</span>;
    }

    render(<MissingDialog />);
    fireEvent.keyDown(document, { key: 'Tab' });
    act(() => { vi.runOnlyPendingTimers(); });
  });

  it('restores an existing opener immediately and on the follow-up timer', () => {
    vi.useFakeTimers();
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();

    function Dialog() {
      const dialogRef = useDialogAccessibility(true, vi.fn());
      return <div ref={dialogRef} role="dialog" tabIndex={-1}><button>inside</button></div>;
    }

    const { unmount } = render(<Dialog />);
    act(() => { vi.runOnlyPendingTimers(); });
    expect(screen.getByRole('button', { name: 'inside' })).toHaveFocus();
    unmount();
    expect(opener).toHaveFocus();
    act(() => { vi.runOnlyPendingTimers(); });
    expect(opener).toHaveFocus();
    opener.remove();
  });

  it('does not wrap Tab from a middle control and tolerates body focus events', async () => {
    function ThreeControlDialog() {
      const dialogRef = useDialogAccessibility(true, vi.fn());
      return (
        <div ref={dialogRef} role="dialog" tabIndex={-1}>
          <button>first</button><button>middle</button><button>last</button>
        </div>
      );
    }

    render(<ThreeControlDialog />);
    const middle = screen.getByRole('button', { name: 'middle' });
    await waitFor(() => expect(screen.getByRole('button', { name: 'first' })).toHaveFocus());
    middle.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(middle).toHaveFocus();
    fireEvent.focusIn(document.body);
    fireEvent.mouseDown(document.body);
  });

  it('moves focus to a stable fallback when the opener is removed after cleanup', () => {
    vi.useFakeTimers();
    const opener = document.createElement('button');
    const fallback = document.createElement('main');
    fallback.tabIndex = -1;
    fallback.dataset.dialogFocusFallback = '';
    document.body.append(opener, fallback);
    opener.focus();

    function Dialog() {
      const dialogRef = useDialogAccessibility(true, vi.fn());
      return <div ref={dialogRef} role="dialog" tabIndex={-1}><button>inside</button></div>;
    }

    const { unmount } = render(<Dialog />);
    act(() => { vi.runOnlyPendingTimers(); });
    unmount();
    opener.remove();
    act(() => { vi.runOnlyPendingTimers(); });
    expect(fallback).toHaveFocus();
    fallback.remove();
  });

  it('focuses the stable region when a destructive close removes its opener', async () => {
    function Harness() {
      const [hasSelection, setHasSelection] = useState(true);
      const [isOpen, setIsOpen] = useState(false);

      return (
        <>
          <aside data-dialog-focus-fallback tabIndex={-1} aria-label="속성 패널">
            {hasSelection ? (
              <button type="button" onClick={() => setIsOpen(true)}>
                선택 항목 편집
              </button>
            ) : (
              <span>선택 없음</span>
            )}
          </aside>
          {isOpen ? (
            <ModalShell
              title="선택 항목 편집"
              titleId="destructive-focus-title"
              onClose={() => setIsOpen(false)}
              closeLabel="편집 닫기"
              size="relationship"
              footer={
                <button
                  type="button"
                  onClick={() => {
                    setHasSelection(false);
                    setIsOpen(false);
                  }}
                >
                  삭제
                </button>
              }
            >
              <span>편집 내용</span>
            </ModalShell>
          ) : null}
        </>
      );
    }

    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole('button', { name: '선택 항목 편집' }));
    await user.click(screen.getByRole('button', { name: '삭제' }));

    await waitFor(() =>
      expect(screen.getByRole('complementary', { name: '속성 패널' })).toHaveFocus(),
    );
  });
});
