import React from 'react';
import { useDialogAccessibility } from './useDialogAccessibility';
import { Toast } from '../Toast';

interface ExportModalProps {
  isOpen: boolean;
  exportDdlText: string;
  isCopied: boolean;
  hasDdlExport: boolean;
  shareLinkUrl: string;
  isCreatingShareLink: boolean;
  isShareLinkCopied: boolean;
  shareLinkError: string | null;
  canCreateShareLink: boolean;
  onCloseExport: () => void;
  onCopyExportDdl: () => void;
  onCreateShareLink: () => void;
  onCopyShareLink: () => void;
}

export function ExportModal({
  isOpen,
  exportDdlText,
  isCopied,
  hasDdlExport,
  shareLinkUrl,
  isCreatingShareLink,
  isShareLinkCopied,
  shareLinkError,
  canCreateShareLink,
  onCloseExport,
  onCopyExportDdl,
  onCreateShareLink,
  onCopyShareLink,
}: ExportModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onCloseExport);
  const toastMessage = isShareLinkCopied
    ? '공유 링크를 복사했습니다.'
    : isCopied
      ? 'DDL을 복사했습니다.'
      : null;

  if (!isOpen) return null;

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
              프로젝트 공유 링크를 만들고 현재 ERD의 DDL을 복사합니다.
            </p>
          </div>
          <button type="button" onClick={onCloseExport}>닫기</button>
        </div>

        <section className="exportModal__section" aria-labelledby="share-link-title">
          <div className="exportModal__sectionHeader">
            <div>
              <h4 id="share-link-title">공유 링크</h4>
              <p>읽기 가능한 스냅샷과 내보내기 API로 연결되는 프로젝트 링크입니다.</p>
            </div>
            <button
              type="button"
              onClick={onCreateShareLink}
              disabled={!canCreateShareLink || isCreatingShareLink}
              aria-busy={isCreatingShareLink}
            >
              {isCreatingShareLink ? "생성 중..." : "링크 만들기"}
            </button>
          </div>

          {shareLinkUrl ? (
            <div className="exportModal__shareResult">
              <input
                readOnly
                aria-label="공유 링크 URL"
                value={shareLinkUrl}
              />
              <button
                type="button"
                onClick={onCopyShareLink}
                aria-live="polite"
              >
                {isShareLinkCopied ? "복사 완료" : "링크 복사"}
              </button>
            </div>
          ) : (
            <span className="field-hint">
              프로젝트가 선택되면 서버에서 새 공유 링크를 발급할 수 있습니다.
            </span>
          )}

          {shareLinkError ? (
            <div className="error" role="alert">{shareLinkError}</div>
          ) : null}
        </section>

        <section className="exportModal__section" aria-labelledby="export-ddl-title">
          <div className="exportModal__sectionHeader">
            <div>
              <h4 id="export-ddl-title">DDL 내보내기</h4>
              <p>현재 캔버스의 테이블, 컬럼, 관계를 SQL DDL 텍스트로 복사합니다.</p>
            </div>
            <button
              type="button"
              onClick={onCopyExportDdl}
              disabled={!hasDdlExport}
              aria-live="polite"
            >
              {isCopied ? "복사 완료" : "DDL 복사"}
            </button>
          </div>

          {hasDdlExport ? (
            <textarea
              readOnly
              aria-label="DDL Export"
              value={exportDdlText}
              className="exportModal__ddl"
            />
          ) : (
            <span className="field-hint">
              DDL을 만들려면 먼저 스냅샷을 생성하거나 테이블을 추가하세요.
            </span>
          )}
        </section>
        {toastMessage ? <Toast message={toastMessage} tone="success" /> : null}
      </div>
    </div>
  );
}
