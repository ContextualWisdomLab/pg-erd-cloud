import '@testing-library/jest-dom/vitest';
import { cleanup, createEvent, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ExportModal } from './ExportModal';

const exportModalProps = {
  isOpen: true,
  isCopied: false,
  hasDdlExport: true,
  hasDictionaryExport: true,
  hasDiagramExport: true,
  shareLinkUrl: '',
  isCreatingShareLink: false,
  isShareLinkCopied: false,
  shareLinkError: null,
  canCreateShareLink: false,
  onCloseExport: vi.fn(),
  onCopyExportDdl: vi.fn(),
  onDownloadSvg: vi.fn(),
  onDownloadUml: vi.fn(),
  onDownloadMermaid: vi.fn(),
  onExportDictionaryCsv: vi.fn(),
  onExportDictionaryMarkdown: vi.fn(),
  onDownloadDbml: vi.fn(),
  onDownloadPrisma: vi.fn(),
  onCreateShareLink: vi.fn(),
  onCopyShareLink: vi.fn(),
};

afterEach(cleanup);

describe('ExportModal disabled access guidance', () => {
  it('keeps the explained disabled action keyboard reachable', () => {
    render(<ExportModal {...exportModalProps} />);

    const accessManagementButton = screen.getByRole('button', { name: '접근 관리' });
    expect(accessManagementButton).toHaveAttribute('aria-disabled', 'true');
    expect(accessManagementButton).toHaveAttribute(
      'aria-describedby',
      'share-export-access-hint',
    );
    expect(accessManagementButton.tabIndex).toBeGreaterThanOrEqual(0);

    accessManagementButton.focus();
    expect(accessManagementButton).toHaveFocus();

    const clickEvent = createEvent.click(accessManagementButton);
    fireEvent(accessManagementButton, clickEvent);
    expect(clickEvent.defaultPrevented).toBe(true);
  });
});
