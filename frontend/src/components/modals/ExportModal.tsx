import React from 'react';
import { useDialogAccessibility } from './useDialogAccessibility';

interface ExportModalProps {
  isOpen: boolean;
  isCopied: boolean;
  hasDdlExport: boolean;
  hasDictionaryExport: boolean;
  hasDiagramExport: boolean;
  shareLinkUrl: string;
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
  hasDictionaryExport,
  hasDiagramExport,
  shareLinkUrl,
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
  onCreateShareLink,
  onCopyShareLink,
}: ExportModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onCloseExport);

  if (!isOpen) return null;

  const shareStatusKind = shareLinkError ? 'error' : isShareLinkCopied ? 'success' : 'neutral';
  const shareStatusRole = shareLinkError ? 'alert' : 'status';
  const shareStatusLive = shareLinkError ? 'assertive' : 'polite';
  const shareStatusMessage = shareLinkError
    ? shareLinkError
    : isShareLinkCopied
      ? '링크가 복사되었습니다. 접근 권한이 있는 팀원이 최신 스냅샷을 열 수 있습니다.'
      : '선택한 다이어그램을 공유하거나 산출물로 내보낼 준비가 되었습니다.';

  const artifacts: ExportArtifact[] = [
    {
      label: 'SQL DDL',
      description: hasDdlExport ? '스키마 텍스트' : '먼저 테이블을 추가하세요',
      buttonLabel: isCopied ? '복사 완료' : '내보내기',
      disabled: !hasDdlExport,
      onExport: onCopyExportDdl,
      ariaLabel: 'SQL DDL 복사',
    },
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
    <div className="modalOverlay">
      <div
        className="modalContent exportModal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="share-export-title"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="modalHeader">
          <div>
            <h3 id="share-export-title">공유 및 내보내기</h3>
            <p className="modalLead">
              공유 링크를 만들거나 현재 ERD를 작업 가능한 산출물로 내보냅니다.
            </p>
          </div>
          <button
            type="button"
            className="exportModal__iconButton"
            aria-label="공유 및 내보내기 닫기"
            onClick={onCloseExport}
          >
            X
          </button>
        </div>

        <div className="exportModal__body">
          <section className="exportModal__section" aria-labelledby="share-link-title">
            <h4 id="share-link-title">공유 링크</h4>
            <p>
              팀원이 검토할 수 있는 API 기반 프로젝트 링크를 생성합니다. 복사
              피드백은 작업 후에도 확인할 수 있게 유지합니다.
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
                  className="exportModal__primaryAction"
                  onClick={onCopyShareLink}
                >
                  {isShareLinkCopied ? '복사 완료' : '링크 복사'}
                </button>
              ) : (
                <button
                  type="button"
                  className="exportModal__primaryAction"
                  onClick={onCreateShareLink}
                  disabled={!canCreateShareLink || isCreatingShareLink}
                  aria-busy={isCreatingShareLink}
                >
                  {isCreatingShareLink ? '생성 중...' : '링크 만들기'}
                </button>
              )}
              <button
                type="button"
                disabled
                aria-describedby="share-export-access-hint"
                className="exportModal__disabledHintButton"
              >
                접근 관리
              </button>
              <p id="share-export-access-hint" className="exportModal__hint">
                접근 권한 관리는 프로젝트 권한 설정에서 처리합니다.
              </p>
            </div>
          </section>

          <section className="exportModal__section" aria-labelledby="export-artifacts-title">
            <h4 id="export-artifacts-title">내보내기 산출물</h4>
            <p>
              공유 링크와 즉시 다운로드되는 캔버스 산출물을 분리해 무엇이
              프로젝트 밖으로 나가는지 명확히 합니다.
            </p>

            <div className="exportModal__artifactList">
              {artifacts.map((artifact) => (
                <div className="exportModal__artifactRow" key={artifact.label}>
                  <div>
                    <strong>{artifact.label}</strong>
                    <span>{artifact.description}</span>
                  </div>
                  <button
                    type="button"
                    onClick={artifact.onExport}
                    disabled={artifact.disabled}
                    aria-label={artifact.ariaLabel}
                    aria-live={artifact.label === 'SQL DDL' ? 'polite' : undefined}
                  >
                    {artifact.buttonLabel}
                  </button>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div
          className={`exportModal__state exportModal__state--${shareStatusKind}`}
          role={shareStatusRole}
          aria-live={shareStatusLive}
        >
          {shareStatusMessage}
        </div>

        <div className="exportModal__footer">
          <button type="button" aria-label="내보내기 취소" onClick={onCloseExport}>취소</button>
          <button type="button" className="exportModal__primaryAction" onClick={onCloseExport}>
            완료
          </button>
        </div>
      </div>
    </div>
  );
}
