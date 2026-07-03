import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ExportModal } from './ExportModal';

const baseProps = {
  isOpen: true,
  exportDdlText: 'create table users (id integer primary key);',
  isCopied: false,
  hasDdlExport: true,
  shareLinkUrl: '',
  isCreatingShareLink: false,
  isShareLinkCopied: false,
  shareLinkError: null,
  canCreateShareLink: true,
  onCloseExport: vi.fn(),
  onCopyExportDdl: vi.fn(),
  onCreateShareLink: vi.fn(),
  onCopyShareLink: vi.fn(),
};

afterEach(() => {
  cleanup();
});

describe('ExportModal', () => {
  it('creates a project share link and exposes the current DDL', () => {
    const onCreateShareLink = vi.fn();
    render(
      <ExportModal
        {...baseProps}
        onCreateShareLink={onCreateShareLink}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '링크 만들기' }));

    expect(onCreateShareLink).toHaveBeenCalledOnce();
    expect(screen.getByLabelText('DDL Export')).toHaveValue(baseProps.exportDdlText);
  });

  it('copies an already generated share link', () => {
    const onCopyShareLink = vi.fn();
    render(
      <ExportModal
        {...baseProps}
        shareLinkUrl="http://localhost/api/share/share-123"
        onCopyShareLink={onCopyShareLink}
      />,
    );

    expect(screen.getByLabelText('공유 링크 URL')).toHaveValue(
      'http://localhost/api/share/share-123',
    );
    fireEvent.click(screen.getByRole('button', { name: '링크 복사' }));

    expect(onCopyShareLink).toHaveBeenCalledOnce();
  });

  it('shows share link copy or creation errors', () => {
    render(
      <ExportModal
        {...baseProps}
        shareLinkError="공유 링크 복사에 실패했습니다."
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('공유 링크 복사에 실패했습니다.');
  });

  it('explains when DDL cannot be generated yet', () => {
    render(
      <ExportModal
        {...baseProps}
        exportDdlText=""
        hasDdlExport={false}
      />,
    );

    expect(screen.queryByLabelText('DDL Export')).not.toBeInTheDocument();
    expect(screen.getByText('DDL을 만들려면 먼저 스냅샷을 생성하거나 테이블을 추가하세요.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'DDL 복사' })).toBeDisabled();
  });
});
