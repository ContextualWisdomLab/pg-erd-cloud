import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ExportModal } from './ExportModal';

const baseProps = {
  isOpen: true,
  isCopied: false,
  hasDdlExport: true,
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

  it('runs each export artifact action from the modal', () => {
    const onCopyExportDdl = vi.fn();
    const onDownloadSvg = vi.fn();
    const onDownloadUml = vi.fn();
    const onDownloadMermaid = vi.fn();

    render(
      <ExportModal
        {...baseProps}
        onCopyExportDdl={onCopyExportDdl}
        onDownloadSvg={onDownloadSvg}
        onDownloadUml={onDownloadUml}
        onDownloadMermaid={onDownloadMermaid}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'SQL DDL 복사' }));
    fireEvent.click(screen.getByRole('button', { name: 'SVG 이미지 내보내기' }));
    fireEvent.click(screen.getByRole('button', { name: 'PlantUML 내보내기' }));
    fireEvent.click(screen.getByRole('button', { name: 'Mermaid 내보내기' }));

    expect(onCopyExportDdl).toHaveBeenCalledOnce();
    expect(onDownloadSvg).toHaveBeenCalledOnce();
    expect(onDownloadUml).toHaveBeenCalledOnce();
    expect(onDownloadMermaid).toHaveBeenCalledOnce();
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
    render(
      <ExportModal
        {...baseProps}
        hasDdlExport={false}
        hasDiagramExport={false}
      />,
    );

    expect(screen.getAllByText('먼저 테이블을 추가하세요')).toHaveLength(4);
    expect(screen.getByRole('button', { name: 'SQL DDL 복사' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'SVG 이미지 내보내기' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'PlantUML 내보내기' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Mermaid 내보내기' })).toBeDisabled();
  });

  it('exposes access-control guidance for disabled button', () => {
    render(<ExportModal {...baseProps} canCreateShareLink={false} />);

    expect(screen.getByText('접근 권한 관리는 프로젝트 권한 설정에서 처리합니다.')).toBeInTheDocument();
    const accessManagementButton = screen.getByRole('button', { name: '접근 관리' });
    expect(accessManagementButton).toBeDisabled();
    expect(accessManagementButton).toHaveAttribute('aria-describedby', 'share-export-access-hint');
    expect(accessManagementButton).not.toHaveAttribute('title');
  });
});
