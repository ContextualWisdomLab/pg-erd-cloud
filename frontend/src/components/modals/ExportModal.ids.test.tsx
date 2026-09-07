import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
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

afterEach(cleanup);

describe('ExportModal artifact description ids', () => {
  it('uses stable artifact identities rather than user-visible labels for aria relationships', () => {
    render(<ExportModal {...baseProps} />);

    const expectedIds = new Map<string, string>([
      ['SQL DDL 복사', 'export-artifact-desc-sql-ddl'],
      ['SVG 이미지 내보내기', 'export-artifact-desc-svg'],
      ['PlantUML 내보내기', 'export-artifact-desc-plantuml'],
      ['Mermaid 내보내기', 'export-artifact-desc-mermaid'],
      ['DBML 내보내기', 'export-artifact-desc-dbml'],
      ['Prisma Schema 내보내기', 'export-artifact-desc-prisma'],
      ['데이터 사전 CSV 내보내기', 'export-artifact-desc-dictionary-csv'],
      ['데이터 사전 Markdown 내보내기', 'export-artifact-desc-dictionary-markdown'],
    ]);

    for (const [buttonName, descriptionId] of expectedIds) {
      expect(screen.getByRole('button', { name: buttonName })).toHaveAttribute(
        'aria-describedby',
        descriptionId,
      );
      expect(document.getElementById(descriptionId)).toBeInTheDocument();
    }
  });
});
