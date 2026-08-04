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

  it('runs each export artifact action from the modal', async () => {
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

    const enabledButtons = [
      screen.getByRole('button', { name: 'SQL DDL 복사' }),
      screen.getByRole('button', { name: 'SVG 이미지 내보내기' }),
      screen.getByRole('button', { name: 'PlantUML 내보내기' }),
      screen.getByRole('button', { name: 'Mermaid 내보내기' }),
      screen.getByRole('button', { name: 'DBML 내보내기' }),
      screen.getByRole('button', { name: 'Prisma Schema 내보내기' }),
      screen.getByRole('button', { name: '데이터 사전 CSV 내보내기' }),
      screen.getByRole('button', { name: '데이터 사전 Markdown 내보내기' }),
    ];

    for (const button of enabledButtons) {
      await user.click(button);
      await user.keyboard('{Enter}');
      await user.keyboard(' ');
    }

    expect(onCopyExportDdl).toHaveBeenCalledTimes(3);
    expect(onDownloadSvg).toHaveBeenCalledTimes(3);
    expect(onDownloadUml).toHaveBeenCalledTimes(3);
    expect(onDownloadMermaid).toHaveBeenCalledTimes(3);
    expect(onDownloadDbml).toHaveBeenCalledTimes(3);
    expect(onDownloadPrisma).toHaveBeenCalledTimes(3);
    expect(onExportDictionaryCsv).toHaveBeenCalledTimes(3);
    expect(onExportDictionaryMarkdown).toHaveBeenCalledTimes(3);
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

  it('explains when exports cannot be generated yet', async () => {
    const user = userEvent.setup();
    render(
      <ExportModal
        {...baseProps}
        hasDdlExport={false}
        hasDictionaryExport={false}
        hasDiagramExport={false}
      />,
    );

    expect(screen.getAllByText('먼저 테이블을 추가하세요')).toHaveLength(8);

    const disabledButtons = [
      'SQL DDL 복사', 'SVG 이미지 내보내기', 'PlantUML 내보내기', 'Mermaid 내보내기',
      'DBML 내보내기', 'Prisma Schema 내보내기', '데이터 사전 CSV 내보내기', '데이터 사전 Markdown 내보내기'
    ];

    for (const name of disabledButtons) {
      const button = screen.getByRole('button', { name });
      expect(button).toHaveAttribute('aria-disabled', 'true');
      button.focus();
      expect(button).toHaveFocus();
      await user.click(button);
      await user.keyboard('{Enter}');
      await user.keyboard(' ');
    }

    expect(baseProps.onCopyExportDdl).not.toHaveBeenCalled();
    expect(baseProps.onDownloadSvg).not.toHaveBeenCalled();
    expect(baseProps.onDownloadUml).not.toHaveBeenCalled();
    expect(baseProps.onDownloadMermaid).not.toHaveBeenCalled();
    expect(baseProps.onDownloadDbml).not.toHaveBeenCalled();
    expect(baseProps.onDownloadPrisma).not.toHaveBeenCalled();
    expect(baseProps.onExportDictionaryCsv).not.toHaveBeenCalled();
    expect(baseProps.onExportDictionaryMarkdown).not.toHaveBeenCalled();
  });

  it('exposes access-control guidance for disabled button', async () => {
    const user = userEvent.setup();
    render(<ExportModal {...baseProps} canCreateShareLink={false} />);

    expect(screen.getByText('접근 권한 관리는 프로젝트 권한 설정에서 처리합니다.')).toBeInTheDocument();
    const accessManagementButton = screen.getByRole('button', { name: '접근 관리' });
    expect(accessManagementButton).toHaveAttribute('aria-disabled', 'true');
    expect(accessManagementButton).toHaveAttribute('aria-describedby', 'share-export-access-hint');
    expect(accessManagementButton).not.toHaveAttribute('title');

    accessManagementButton.focus();
    expect(accessManagementButton).toHaveFocus();
    await user.click(accessManagementButton);
    await user.keyboard('{Enter}');
    await user.keyboard(' ');

    expect(baseProps.onCloseExport).not.toHaveBeenCalled();
  });
});
