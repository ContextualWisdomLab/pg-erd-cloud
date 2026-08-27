import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ExportModal } from './ExportModal';

const baseProps = {
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

afterEach(() => {
  cleanup();
});

describe('ExportModal', () => {
  it('separates project share links from export artifacts', () => {
    const onCreateShareLink = vi.fn();
    render(
      <ExportModal
        {...baseProps}
        onCreateShareLink={onCreateShareLink}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '링크 만들기' }));

    expect(onCreateShareLink).toHaveBeenCalledOnce();
    expect(screen.getByRole('heading', { name: '공유 링크' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '내보내기 산출물' })).toBeInTheDocument();
    expect(screen.getByText('SQL DDL')).toBeInTheDocument();
    expect(screen.getByText('SVG 이미지')).toBeInTheDocument();
    expect(screen.getByText('PlantUML')).toBeInTheDocument();
    expect(screen.getByText('Mermaid')).toBeInTheDocument();
    expect(screen.getByText('DBML')).toBeInTheDocument();
    expect(screen.getByText('Prisma Schema')).toBeInTheDocument();
    expect(screen.getByText('Data Dictionary CSV')).toBeInTheDocument();
    expect(screen.getByText('Data Dictionary MD')).toBeInTheDocument();
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

  it('shows copied and in-progress status variants', () => {
    const { rerender } = render(
      <ExportModal
        {...baseProps}
        isCopied
        isShareLinkCopied
        shareLinkUrl="http://localhost/api/share/copied"
      />,
    );
    expect(screen.getByRole('button', { name: '복사 완료' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('링크가 복사되었습니다');

    rerender(
      <ExportModal
        {...baseProps}
        isCreatingShareLink
      />,
    );
    expect(screen.getByRole('button', { name: '생성 중...' })).toBeDisabled();
  });

  it('keeps unavailable share-link creation discoverable and inert until a project is selected', async () => {
    const onCreateShareLink = vi.fn();
    const user = userEvent.setup();
    render(
      <ExportModal
        {...baseProps}
        canCreateShareLink={false}
        onCreateShareLink={onCreateShareLink}
      />,
    );

    const createShareLinkButton = screen.getByRole('button', { name: '링크 만들기' });
    expect(createShareLinkButton).not.toBeDisabled();
    expect(createShareLinkButton).toHaveAttribute('aria-disabled', 'true');
    expect(createShareLinkButton).toHaveAttribute('aria-describedby', 'share-link-create-hint');
    expect(screen.getByText('먼저 프로젝트를 선택하세요.')).toBeVisible();

    createShareLinkButton.focus();
    expect(createShareLinkButton).toHaveFocus();
    await user.click(createShareLinkButton);
    await user.keyboard('{Enter}');
    await user.keyboard(' ');

    expect(onCreateShareLink).not.toHaveBeenCalled();
  });

  it('runs each export artifact action exactly once for click, Enter, and Space', async () => {
    const onCopyExportDdl = vi.fn();
    const onDownloadSvg = vi.fn();
    const onDownloadUml = vi.fn();
    const onDownloadMermaid = vi.fn();
    const onExportDictionaryCsv = vi.fn();
    const onExportDictionaryMarkdown = vi.fn();
    const onDownloadDbml = vi.fn();
    const onDownloadPrisma = vi.fn();
    const user = userEvent.setup();

    render(
      <ExportModal
        {...baseProps}
        onCopyExportDdl={onCopyExportDdl}
        onDownloadSvg={onDownloadSvg}
        onDownloadUml={onDownloadUml}
        onDownloadMermaid={onDownloadMermaid}
        onExportDictionaryCsv={onExportDictionaryCsv}
        onExportDictionaryMarkdown={onExportDictionaryMarkdown}
        onDownloadDbml={onDownloadDbml}
        onDownloadPrisma={onDownloadPrisma}
      />,
    );

    const enabledActions = [
      { button: screen.getByRole('button', { name: 'SQL DDL 복사' }), callback: onCopyExportDdl },
      { button: screen.getByRole('button', { name: 'SVG 이미지 내보내기' }), callback: onDownloadSvg },
      { button: screen.getByRole('button', { name: 'PlantUML 내보내기' }), callback: onDownloadUml },
      { button: screen.getByRole('button', { name: 'Mermaid 내보내기' }), callback: onDownloadMermaid },
      { button: screen.getByRole('button', { name: 'DBML 내보내기' }), callback: onDownloadDbml },
      { button: screen.getByRole('button', { name: 'Prisma Schema 내보내기' }), callback: onDownloadPrisma },
      { button: screen.getByRole('button', { name: '데이터 사전 CSV 내보내기' }), callback: onExportDictionaryCsv },
      { button: screen.getByRole('button', { name: '데이터 사전 Markdown 내보내기' }), callback: onExportDictionaryMarkdown },
    ];

    for (const { button, callback } of enabledActions) {
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

  it('shows share link copy or creation errors', () => {
    render(
      <ExportModal
        {...baseProps}
        shareLinkError="공유 링크 복사에 실패했습니다."
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('공유 링크 복사에 실패했습니다.');
  });

  it('explains and suppresses every export that cannot be generated yet', async () => {
    const onCopyExportDdl = vi.fn();
    const onDownloadSvg = vi.fn();
    const onDownloadUml = vi.fn();
    const onDownloadMermaid = vi.fn();
    const onExportDictionaryCsv = vi.fn();
    const onExportDictionaryMarkdown = vi.fn();
    const onDownloadDbml = vi.fn();
    const onDownloadPrisma = vi.fn();
    const user = userEvent.setup();
    render(
      <ExportModal
        {...baseProps}
        hasDdlExport={false}
        hasDictionaryExport={false}
        hasDiagramExport={false}
        onCopyExportDdl={onCopyExportDdl}
        onDownloadSvg={onDownloadSvg}
        onDownloadUml={onDownloadUml}
        onDownloadMermaid={onDownloadMermaid}
        onExportDictionaryCsv={onExportDictionaryCsv}
        onExportDictionaryMarkdown={onExportDictionaryMarkdown}
        onDownloadDbml={onDownloadDbml}
        onDownloadPrisma={onDownloadPrisma}
      />,
    );

    expect(screen.getAllByText('먼저 테이블을 추가하세요')).toHaveLength(8);

    const disabledButtons = [
      'SQL DDL 복사',
      'SVG 이미지 내보내기',
      'PlantUML 내보내기',
      'Mermaid 내보내기',
      'DBML 내보내기',
      'Prisma Schema 내보내기',
      '데이터 사전 CSV 내보내기',
      '데이터 사전 Markdown 내보내기',
    ];
    const descriptionIds = new Set<string>();

    for (const name of disabledButtons) {
      const button = screen.getByRole('button', { name });
      expect(button).toHaveAttribute('aria-disabled', 'true');

      const descriptionId = button.getAttribute('aria-describedby');
      expect(descriptionId).toBeTruthy();
      expect(descriptionIds.has(descriptionId!)).toBe(false);
      descriptionIds.add(descriptionId!);

      const description = document.getElementById(descriptionId!);
      expect(description).toBeVisible();
      expect(description).toHaveTextContent('먼저 테이블을 추가하세요');

      button.focus();
      expect(button).toHaveFocus();
      await user.click(button);
      await user.keyboard('{Enter}');
      await user.keyboard(' ');
    }

    expect(descriptionIds.size).toBe(8);
    expect(onCopyExportDdl).not.toHaveBeenCalled();
    expect(onDownloadSvg).not.toHaveBeenCalled();
    expect(onDownloadUml).not.toHaveBeenCalled();
    expect(onDownloadMermaid).not.toHaveBeenCalled();
    expect(onDownloadDbml).not.toHaveBeenCalled();
    expect(onDownloadPrisma).not.toHaveBeenCalled();
    expect(onExportDictionaryCsv).not.toHaveBeenCalled();
    expect(onExportDictionaryMarkdown).not.toHaveBeenCalled();
  });

  it('exposes access-control guidance and prevents each activation method', async () => {
    const user = userEvent.setup();
    const observedDefaultPrevention = vi.fn();
    render(
      <div onClick={(event) => observedDefaultPrevention(event.defaultPrevented)}>
        <ExportModal {...baseProps} canCreateShareLink={false} />
      </div>,
    );

    expect(screen.getByText('접근 권한 관리는 프로젝트 권한 설정에서 처리합니다.')).toBeInTheDocument();
    const accessManagementButton = screen.getByRole('button', { name: '접근 관리' });
    expect(accessManagementButton).toHaveAttribute('aria-disabled', 'true');
    expect(accessManagementButton).toHaveAttribute('aria-describedby', 'share-export-access-hint');
    expect(accessManagementButton).not.toHaveAttribute('title');

    accessManagementButton.focus();
    expect(accessManagementButton).toHaveFocus();

    await user.click(accessManagementButton);
    expect(observedDefaultPrevention).toHaveBeenCalledTimes(1);
    expect(observedDefaultPrevention).toHaveBeenLastCalledWith(true);

    accessManagementButton.focus();
    await user.keyboard('{Enter}');
    expect(observedDefaultPrevention).toHaveBeenCalledTimes(2);
    expect(observedDefaultPrevention).toHaveBeenLastCalledWith(true);

    accessManagementButton.focus();
    await user.keyboard(' ');
    expect(observedDefaultPrevention).toHaveBeenCalledTimes(3);
    expect(observedDefaultPrevention).toHaveBeenLastCalledWith(true);
  });
});
