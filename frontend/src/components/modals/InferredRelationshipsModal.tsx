import React from 'react';
import type { InferredRelationship } from '../../types';
import { useDialogAccessibility } from './useDialogAccessibility';

interface InferredRelationshipsModalProps {
  isOpen: boolean;
  relationships: InferredRelationship[];
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
}

export function InferredRelationshipsModal({
  isOpen,
  relationships,
  isLoading,
  error,
  onClose,
}: InferredRelationshipsModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onClose);
  if (!isOpen) return null;

  return (
    <div className="modalOverlay">
      <div
        className="modalContent inferredModal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="inferred-title"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="modalHeader">
          <div>
            <h3 id="inferred-title">추론된 관계</h3>
            <p className="modalLead">
              선언되지 않은 외래키를 이름 규칙으로 추론합니다. 참고용이며 실제 제약이 아닙니다.
            </p>
          </div>
          <button type="button" onClick={onClose}>닫기</button>
        </div>

        {isLoading ? (
          <span className="field-hint" role="status">분석 중…</span>
        ) : null}
        {error ? (
          <div className="error" role="alert">{error}</div>
        ) : null}

        {!isLoading && !error ? (
          <section className="inferredModal__list" aria-label="추론된 관계 목록">
            {relationships.length === 0 ? (
              <span className="field-hint">추론된 관계가 없습니다.</span>
            ) : (
              <ul>
                {relationships.map((r, i) => (
                  <li
                    key={`${r.child_schema}.${r.child_table}.${r.child_column}-${i}`}
                    className="inferredModal__item"
                    title={r.reason}
                  >
                    <span className="inferredModal__rel">
                      {r.child_table}.{r.child_column} → {r.parent_table}.
                      {r.parent_column}
                    </span>
                    <span
                      className={
                        r.confidence === 'high'
                          ? 'statusPill statusPill--succeeded'
                          : 'statusPill'
                      }
                    >
                      {r.confidence === 'high' ? '높음' : '보통'}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : null}
      </div>
    </div>
  );
}
