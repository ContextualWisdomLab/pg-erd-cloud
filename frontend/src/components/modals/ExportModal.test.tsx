import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ExportModal } from './ExportModal';

const baseProps = {
  isOpen: true,
  isCopied: false,
  hasDdlExport: true,
  ddlText: 'CREATE TABLE users ();',
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
  it('renders the Figma share and DDL sections while preserving extra artifacts', () => {
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
    expect(screen.getByRole('heading', { name: 'DDL 내보내기' })).toBeInTheDocument();
    expect(screen.getByLabelText('DDL SQL')).toHaveValue('CREATE TABLE users ();');
    expect(
      screen.getByRole('button', { name: 'SQL DDL 복사' }).closest('.modalShell__footer'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText('기타 산출물'));
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
        shareLinkUrl="http://localhost/share/share-123"
        onCopyShareLink={onCopyShareLink}
      />,
    );

    expect(screen.getByLabelText('공유 링크 URL')).toHaveValue(
      'http://localhost/share/share-123',
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
    expect(screen.getByRole('status')).toHaveTextContent('복사 완료');

    rerender(
      <ExportModal
        {...baseProps}
        isCreatingShareLink
      />,
    );
    expect(screen.getByRole('button', { name: '생성 중...' })).toBeDisabled();
  });

  it('runs each export artifact action from the modal', () => {
    const onCopyExportDdl = vi.fn();
    const onDownloadSvg = vi.fn();
    const onDownloadUml = vi.fn();
    const onDownloadMermaid = vi.fn();
    const onExportDictionaryCsv = vi.fn();
    const onExportDictionaryMarkdown = vi.fn();
    const onDownloadDbml = vi.fn();
    const onDownloadPrisma = vi.fn();

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

    fireEvent.click(screen.getByText('기타 산출물'));
    fireEvent.click(screen.getByRole('button', { name: 'SQL DDL 복사' }));
    fireEvent.click(screen.getByRole('button', { name: 'SVG 이미지 내보내기' }));
    fireEvent.click(screen.getByRole('button', { name: 'PlantUML 내보내기' }));
    fireEvent.click(screen.getByRole('button', { name: 'Mermaid 내보내기' }));
    fireEvent.click(screen.getByRole('button', { name: 'DBML 내보내기' }));
    fireEvent.click(screen.getByRole('button', { name: 'Prisma Schema 내보내기' }));
    fireEvent.click(screen.getByRole('button', { name: '데이터 사전 CSV 내보내기' }));
    fireEvent.click(screen.getByRole('button', { name: '데이터 사전 Markdown 내보내기' }));

    expect(onCopyExportDdl).toHaveBeenCalledOnce();
    expect(onDownloadSvg).toHaveBeenCalledOnce();
    expect(onDownloadUml).toHaveBeenCalledOnce();
    expect(onDownloadMermaid).toHaveBeenCalledOnce();
    expect(onDownloadDbml).toHaveBeenCalledOnce();
    expect(onDownloadPrisma).toHaveBeenCalledOnce();
    expect(onExportDictionaryCsv).toHaveBeenCalledOnce();
    expect(onExportDictionaryMarkdown).toHaveBeenCalledOnce();
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

  it('explains when exports cannot be generated yet', () => {
    const onCopyExportDdl = vi.fn();
    const onDownloadSvg = vi.fn();
    const onDownloadUml = vi.fn();
    const onDownloadMermaid = vi.fn();
    const onDownloadDbml = vi.fn();
    const onDownloadPrisma = vi.fn();
    const onExportDictionaryCsv = vi.fn();
    const onExportDictionaryMarkdown = vi.fn();
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
        onDownloadDbml={onDownloadDbml}
        onDownloadPrisma={onDownloadPrisma}
        onExportDictionaryCsv={onExportDictionaryCsv}
        onExportDictionaryMarkdown={onExportDictionaryMarkdown}
      />,
    );

    expect(screen.getByText('DDL을 만들려면 먼저 스냅샷을 생성하거나 테이블을 추가하세요.')).toBeInTheDocument();
    fireEvent.click(screen.getByText('기타 산출물'));
    expect(screen.getAllByText('먼저 테이블을 추가하세요')).toHaveLength(7);
    const unavailableActions = [
      screen.getByRole('button', { name: 'SQL DDL 복사' }),
      screen.getByRole('button', { name: 'SVG 이미지 내보내기' }),
      screen.getByRole('button', { name: 'PlantUML 내보내기' }),
      screen.getByRole('button', { name: 'Mermaid 내보내기' }),
      screen.getByRole('button', { name: 'DBML 내보내기' }),
      screen.getByRole('button', { name: 'Prisma Schema 내보내기' }),
      screen.getByRole('button', { name: '데이터 사전 CSV 내보내기' }),
      screen.getByRole('button', { name: '데이터 사전 Markdown 내보내기' }),
    ];
    unavailableActions.forEach((button) => {
      expect(button).toBeEnabled();
      expect(button).toHaveAttribute('aria-disabled', 'true');
      expect(button).toHaveAttribute('aria-describedby');
      fireEvent.click(button);
    });
    expect(onCopyExportDdl).not.toHaveBeenCalled();
    expect(onDownloadSvg).not.toHaveBeenCalled();
    expect(onDownloadUml).not.toHaveBeenCalled();
    expect(onDownloadMermaid).not.toHaveBeenCalled();
    expect(onDownloadDbml).not.toHaveBeenCalled();
    expect(onDownloadPrisma).not.toHaveBeenCalled();
    expect(onExportDictionaryCsv).not.toHaveBeenCalled();
    expect(onExportDictionaryMarkdown).not.toHaveBeenCalled();
  });

  it('warns that bearer share links currently cannot be expired or revoked', () => {
    render(<ExportModal {...baseProps} canCreateShareLink={false} />);

    expect(
      screen.getByText('이 링크를 아는 누구나 공유된 성공 스냅샷을 볼 수 있으며, 현재 링크 만료·회수 기능은 제공되지 않습니다.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '접근 관리' })).not.toBeInTheDocument();
  });
});
