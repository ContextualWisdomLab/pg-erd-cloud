import React from 'react';
import { ModalShell } from './ModalShell';

interface ExportModalProps {
  isOpen: boolean;
  isCopied: boolean;
  hasDdlExport: boolean;
  ddlText: string;
  hasDictionaryExport: boolean;
  hasDiagramExport: boolean;
  shareLinkUrl: string;
  shareLinkExpiresAt: string;
  isCreatingShareLink: boolean;
  isShareLinkCopied: boolean;
  shareLinkError: string | null;
  canCreateShareLink: boolean;
  onCloseExport: () => void;
  onCopyExportDdl: () => void;
  onDownloadSvg: () => void;
  onDownloadUml: () => void;
  onDownloadMermaid: () => void;
  onExportDictionaryCsv: () => void;
  onExportDictionaryMarkdown: () => void;
  onDownloadDbml: () => void;
  onDownloadPrisma: () => void;
  onCreateShareLink: () => void;
  onCopyShareLink: () => void;
}

type ExportArtifact = {
  label: string;
  description: string;
  buttonLabel: string;
  disabled: boolean;
  onExport: () => void;
  ariaLabel: string;
};

export function ExportModal({
  isOpen,
  isCopied,
  hasDdlExport,
  ddlText,
  hasDictionaryExport,
  hasDiagramExport,
  shareLinkUrl,
  shareLinkExpiresAt,
  isCreatingShareLink,
  isShareLinkCopied,
  shareLinkError,
  canCreateShareLink,
  onCloseExport,
  onCopyExportDdl,
  onDownloadSvg,
  onDownloadUml,
  onDownloadMermaid,
  onExportDictionaryCsv,
  onExportDictionaryMarkdown,
  onDownloadDbml,
  onDownloadPrisma,
  onCreateShareLink,
  onCopyShareLink,
}: ExportModalProps) {
  if (!isOpen) return null;

  const expiryDate = shareLinkExpiresAt ? new Date(shareLinkExpiresAt) : null;
  const expiryLabel = expiryDate && !Number.isNaN(expiryDate.getTime())
    ? new Intl.DateTimeFormat('ko-KR', {
        dateStyle: 'long',
        timeStyle: 'short',
      }).format(expiryDate)
    : null;

  const shareStatusKind = shareLinkError ? 'error' : isShareLinkCopied ? 'success' : 'neutral';
  const shareStatusRole = shareLinkError ? 'alert' : 'status';
  const shareStatusLive = shareLinkError ? 'assertive' : 'polite';
  const shareStatusMessage = shareLinkError
    ? shareLinkError
    : isShareLinkCopied
      ? '복사 완료'
      : shareLinkUrl
        ? '공유 링크가 준비되었습니다.'
        : isCreatingShareLink
          ? '공유 링크를 생성하고 있습니다.'
          : '프로젝트가 선택되면 서버에서 새 공유 링크를 발급할 수 있습니다.';

  const artifacts: ExportArtifact[] = [
    {
      label: 'SVG 이미지',
      description: hasDiagramExport ? '다이어그램 파일' : '먼저 테이블을 추가하세요',
      buttonLabel: '내보내기',
      disabled: !hasDiagramExport,
      onExport: onDownloadSvg,
      ariaLabel: 'SVG 이미지 내보내기',
    },
    {
      label: 'PlantUML',
      description: hasDiagramExport ? '텍스트 포맷' : '먼저 테이블을 추가하세요',
      buttonLabel: '내보내기',
      disabled: !hasDiagramExport,
      onExport: onDownloadUml,
      ariaLabel: 'PlantUML 내보내기',
    },
    {
      label: 'Mermaid',
      description: hasDiagramExport ? '텍스트 포맷' : '먼저 테이블을 추가하세요',
      buttonLabel: '내보내기',
      disabled: !hasDiagramExport,
      onExport: onDownloadMermaid,
      ariaLabel: 'Mermaid 내보내기',
    },
    {
      label: 'DBML',
      description: hasDiagramExport ? '텍스트 포맷' : '먼저 테이블을 추가하세요',
      buttonLabel: '내보내기',
      disabled: !hasDiagramExport,
      onExport: onDownloadDbml,
      ariaLabel: 'DBML 내보내기',
    },
    {
      label: 'Prisma Schema',
      description: hasDiagramExport ? '텍스트 포맷' : '먼저 테이블을 추가하세요',
      buttonLabel: '내보내기',
      disabled: !hasDiagramExport,
      onExport: onDownloadPrisma,
      ariaLabel: 'Prisma Schema 내보내기',
    },
    {
      label: 'Data Dictionary CSV',
      description: hasDictionaryExport ? '테이블/컬럼 목록' : '먼저 테이블을 추가하세요',
      buttonLabel: '내보내기',
      disabled: !hasDictionaryExport,
      onExport: onExportDictionaryCsv,
      ariaLabel: '데이터 사전 CSV 내보내기',
    },
    {
      label: 'Data Dictionary MD',
      description: hasDictionaryExport ? '마크다운 문서' : '먼저 테이블을 추가하세요',
      buttonLabel: '내보내기',
      disabled: !hasDictionaryExport,
      onExport: onExportDictionaryMarkdown,
      ariaLabel: '데이터 사전 Markdown 내보내기',
    },
  ];

  return (
    <ModalShell
      title="공유 및 내보내기"
      titleId="share-export-title"
      description="프로젝트 공유 링크를 만들고 현재 ERD의 DDL을 복사합니다."
      onClose={onCloseExport}
      closeLabel="공유 및 내보내기 닫기"
      size="export"
      footer={
        <button
          type="button"
          className="buttonPrimary"
          onClick={() => {
            if (hasDdlExport) onCopyExportDdl();
          }}
          aria-disabled={!hasDdlExport}
          aria-describedby={!hasDdlExport ? 'ddl-export-prerequisite' : undefined}
          aria-label="SQL DDL 복사"
          aria-live="polite"
        >
          {isCopied ? '복사 완료' : 'DDL 복사'}
        </button>
      }
    >
      <div className="exportModal__body">
        <section className="exportModal__section" aria-labelledby="share-link-title">
          <h4 id="share-link-title">공유 링크</h4>
          <p>
            읽기 가능한 스냅샷과 내보내기 API로 연결되는 프로젝트 링크입니다.
          </p>

          <input
            readOnly
            aria-label="공유 링크 URL"
            value={shareLinkUrl}
            placeholder="링크가 아직 생성되지 않았습니다"
            className={shareLinkError ? 'exportModal__linkInput exportModal__linkInput--error' : 'exportModal__linkInput'}
          />

          <div className="exportModal__shareActions">
            {shareLinkUrl ? (
              <button
                type="button"
                className="buttonPrimary"
                onClick={onCopyShareLink}
              >
                {isShareLinkCopied ? '복사 완료' : '링크 복사'}
              </button>
            ) : (
              <button
                type="button"
                className="buttonPrimary"
                onClick={onCreateShareLink}
                disabled={!canCreateShareLink || isCreatingShareLink}
                aria-busy={isCreatingShareLink}
              >
                {isCreatingShareLink ? '생성 중...' : '링크 만들기'}
              </button>
            )}
            <p id="share-export-access-hint" className="exportModal__hint">
              이 링크를 아는 누구나 공유된 성공 스냅샷을 볼 수 있습니다. 새 링크는
              서버가 설정한 시점에 자동 만료되며, 소유자는 프로젝트 공유 API로 즉시
              폐기할 수 있습니다. 현재 이 화면에는 회수 버튼이 없습니다.
              {expiryLabel ? (
                <> 만료 예정: <time dateTime={shareLinkExpiresAt}>{expiryLabel}</time>.</>
              ) : null}
            </p>
          </div>

          <div
            className={`exportModal__state exportModal__state--${shareStatusKind}`}
            role={shareStatusRole}
            aria-live={shareStatusLive}
          >
            {shareStatusMessage}
          </div>
        </section>

        <section className="exportModal__section" aria-labelledby="ddl-export-title">
          <h4 id="ddl-export-title">DDL 내보내기</h4>
          <p>
            현재 캔버스의 테이블, 컬럼, 관계를 SQL DDL 텍스트로 복사합니다.
          </p>
          <textarea
            readOnly
            aria-label="DDL SQL"
            value={ddlText}
            placeholder="DDL을 만들려면 먼저 테이블을 추가하세요."
            className="exportModal__ddl"
          />
          {!hasDdlExport ? (
            <p id="ddl-export-prerequisite" className="exportModal__hint">
              DDL을 만들려면 먼저 스냅샷을 생성하거나 테이블을 추가하세요.
            </p>
          ) : null}
        </section>

        <details className="exportModal__extras">
          <summary>기타 산출물</summary>
          <p>SVG, 텍스트 모델, 데이터 사전을 추가 형식으로 내려받습니다.</p>
          <div className="exportModal__artifactList">
            {artifacts.map((artifact, index) => (
              <div className="exportModal__artifactRow" key={artifact.label}>
                <div>
                  <strong>{artifact.label}</strong>
                  <span id={`export-artifact-hint-${index}`}>{artifact.description}</span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (!artifact.disabled) artifact.onExport();
                  }}
                  aria-disabled={artifact.disabled}
                  aria-describedby={artifact.disabled ? `export-artifact-hint-${index}` : undefined}
                  aria-label={artifact.ariaLabel}
                >
                  {artifact.buttonLabel}
                </button>
              </div>
            ))}
          </div>
        </details>
      </div>
    </ModalShell>
  );
}
