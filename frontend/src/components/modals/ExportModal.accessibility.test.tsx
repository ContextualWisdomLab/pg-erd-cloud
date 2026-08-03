import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ExportModal } from './ExportModal';

function createModalProps() {
  const actions = {
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

  return {
    actions,
    props: {
      isOpen: true,
      isCopied: false,
      hasDdlExport: true,
      hasDictionaryExport: true,
      hasDiagramExport: true,
      shareLinkUrl: '',
      isCreatingShareLink: false,
      isShareLinkCopied: false,
      shareLinkError: null,
      canCreateShareLink: true,
      ...actions,
    },
  };
}

const exportButtons = [
  ['SQL DDL 복사', 'onCopyExportDdl'],
  ['SVG 이미지 내보내기', 'onDownloadSvg'],
  ['PlantUML 내보내기', 'onDownloadUml'],
  ['Mermaid 내보내기', 'onDownloadMermaid'],
  ['DBML 내보내기', 'onDownloadDbml'],
  ['Prisma Schema 내보내기', 'onDownloadPrisma'],
  ['데이터 사전 CSV 내보내기', 'onExportDictionaryCsv'],
  ['데이터 사전 Markdown 내보내기', 'onExportDictionaryMarkdown'],
] as const;

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('ExportModal aria-disabled interactions', () => {
  it('keeps every unavailable export focusable and inert for mouse and keyboard', async () => {
    const user = userEvent.setup();
    const { props, actions } = createModalProps();

    render(
      <ExportModal
        {...props}
        hasDdlExport={false}
        hasDictionaryExport={false}
        hasDiagramExport={false}
      />,
    );

    for (const [name, actionName] of exportButtons) {
      const button = screen.getByRole('button', { name });
      const callback = actions[actionName];
      const descriptionId = button.getAttribute('aria-describedby');

      expect(button).toHaveAttribute('aria-disabled', 'true');
      expect(button).not.toHaveAttribute('title');
      expect(descriptionId).toBeTruthy();
      expect(document.getElementById(descriptionId!)).toHaveTextContent(
        '먼저 테이블을 추가하세요',
      );

      button.focus();
      expect(button).toHaveFocus();
      await user.click(button);
      expect(callback).not.toHaveBeenCalled();

      button.focus();
      await user.keyboard('{Enter}');
      expect(callback).not.toHaveBeenCalled();

      button.focus();
      await user.keyboard(' ');
      expect(callback).not.toHaveBeenCalled();
    }
  });

  it('runs every available export exactly once for each activation', async () => {
    const user = userEvent.setup();
    const { props, actions } = createModalProps();

    render(<ExportModal {...props} />);

    for (const [name, actionName] of exportButtons) {
      const button = screen.getByRole('button', { name });
      const callback = actions[actionName];

      expect(button).not.toHaveAttribute('aria-disabled');

      await user.click(button);
      expect(callback).toHaveBeenCalledTimes(1);

      button.focus();
      await user.keyboard('{Enter}');
      expect(callback).toHaveBeenCalledTimes(2);

      button.focus();
      await user.keyboard(' ');
      expect(callback).toHaveBeenCalledTimes(3);
    }
  });

  it('keeps access management focusable without triggering surrounding actions', async () => {
    const user = userEvent.setup();
    const { props, actions } = createModalProps();

    render(<ExportModal {...props} canCreateShareLink={false} />);

    const button = screen.getByRole('button', { name: '접근 관리' });
    expect(button).toHaveAttribute('aria-disabled', 'true');
    expect(button).toHaveAttribute('aria-describedby', 'share-export-access-hint');
    expect(button).not.toHaveAttribute('title');

    button.focus();
    expect(button).toHaveFocus();
    await user.click(button);
    button.focus();
    await user.keyboard('{Enter}');
    button.focus();
    await user.keyboard(' ');

    for (const callback of Object.values(actions)) {
      expect(callback).not.toHaveBeenCalled();
    }
  });
});
