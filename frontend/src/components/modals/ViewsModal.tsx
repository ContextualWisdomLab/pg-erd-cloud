import React from 'react';
import type { DiagramView } from '../../types';
import { useDialogAccessibility } from './useDialogAccessibility';

interface ViewsModalProps {
  isOpen: boolean;
  views: DiagramView[];
  newViewName: string;
  setNewViewName: (value: string) => void;
  isSaving: boolean;
  error: string | null;
  /** True when there is a layout worth saving (project selected + tables on canvas). */
  canSave: boolean;
  onSaveCurrent: () => void;
  onLoadView: (viewId: string) => void;
  onDeleteView: (viewId: string) => void;
  onClose: () => void;
}

export function ViewsModal({
  isOpen,
  views,
  newViewName,
  setNewViewName,
  isSaving,
  error,
  canSave,
  onSaveCurrent,
  onLoadView,
  onDeleteView,
  onClose,
}: ViewsModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onClose);

  if (!isOpen) return null;

  return (
    <div className="modalOverlay">
      <div
        className="modalContent viewsModal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="views-title"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="modalHeader">
          <div>
            <h3 id="views-title">저장된 뷰</h3>
            <p className="modalLead">
              현재 캔버스 배치를 이름을 지정해 저장하고, 저장한 배치를 다시 불러옵니다.
            </p>
          </div>
          <button type="button" onClick={onClose}>닫기</button>
        </div>

        <section className="viewsModal__save">
          <label htmlFor="view-name-input">현재 배치 저장</label>
          <div className="viewsModal__saveRow">
            <input
              id="view-name-input"
              value={newViewName}
              onChange={(e) => setNewViewName(e.target.value)}
              placeholder="뷰 이름"
              aria-label="뷰 이름"
            />
            <button
              type="button"
              onClick={onSaveCurrent}
              disabled={!canSave || isSaving || newViewName.trim().length === 0}
              aria-busy={isSaving}
            >
              {isSaving ? '저장 중...' : '현재 배치 저장'}
            </button>
          </div>
          {!canSave ? (
            <span className="field-hint">
              프로젝트를 선택하고 캔버스에 테이블이 있어야 저장할 수 있습니다.
            </span>
          ) : null}
        </section>

        {error ? (
          <div className="error" role="alert">{error}</div>
        ) : null}

        <section className="viewsModal__list" aria-label="저장된 뷰 목록">
          {views.length === 0 ? (
            <span className="field-hint">저장된 뷰가 없습니다.</span>
          ) : (
            <ul>
              {views.map((view) => (
                <li key={view.diagram_view_uuid} className="viewsModal__item">
                  <span className="viewsModal__name">{view.name}</span>
                  <span className="viewsModal__actions">
                    <button type="button" onClick={() => onLoadView(view.diagram_view_uuid)}>
                      불러오기
                    </button>
                    <button
                      type="button"
                      onClick={() => onDeleteView(view.diagram_view_uuid)}
                      aria-label={`${view.name} 삭제`}
                    >
                      삭제
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
