import React, { useState } from 'react';
import type { TableAnnotation } from '../../types';
import { useDialogAccessibility } from './useDialogAccessibility';

interface AnnotationsModalProps {
  isOpen: boolean;
  annotations: TableAnnotation[];
  isSaving: boolean;
  error: string | null;
  onSave: (schemaName: string, relationName: string, body: string) => void;
  onDelete: (annotationId: string) => void;
  onClose: () => void;
}

export function AnnotationsModal({
  isOpen,
  annotations,
  isSaving,
  error,
  onSave,
  onDelete,
  onClose,
}: AnnotationsModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onClose);
  const [schemaName, setSchemaName] = useState('public');
  const [relationName, setRelationName] = useState('');
  const [body, setBody] = useState('');

  if (!isOpen) return null;

  const canSave =
    schemaName.trim() !== '' &&
    relationName.trim() !== '' &&
    body.trim() !== '' &&
    !isSaving;

  function handleSave() {
    if (!canSave) return;
    onSave(schemaName.trim(), relationName.trim(), body.trim());
    setBody('');
  }

  function startEdit(annotation: TableAnnotation) {
    setSchemaName(annotation.schema_name);
    setRelationName(annotation.relation_name);
    setBody(annotation.body);
  }

  return (
    <div className="modalOverlay">
      <div
        className="modalContent annotationsModal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="annotations-title"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="modalHeader">
          <div>
            <h3 id="annotations-title">테이블 주석</h3>
            <p className="modalLead">
              테이블에 설명 메모를 남기고 관리합니다. (테이블당 1개, 이름 기준)
            </p>
          </div>
          <button type="button" onClick={onClose}>닫기</button>
        </div>

        <section className="annotationsModal__form">
          <div className="row">
            <input
              aria-label="스키마"
              value={schemaName}
              onChange={(e) => setSchemaName(e.target.value)}
              placeholder="스키마"
            />
            <input
              aria-label="테이블"
              value={relationName}
              onChange={(e) => setRelationName(e.target.value)}
              placeholder="테이블"
            />
          </div>
          <textarea
            aria-label="주석 내용"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="주석 내용"
          />
          <button
            type="button"
            onClick={handleSave}
            disabled={!canSave}
            aria-busy={isSaving}
          >
            {isSaving ? '저장 중...' : '저장'}
          </button>
        </section>

        {error ? (
          <div className="error" role="alert">{error}</div>
        ) : null}

        <section className="annotationsModal__list" aria-label="주석 목록">
          {annotations.length === 0 ? (
            <span className="field-hint">아직 주석이 없습니다.</span>
          ) : (
            <ul>
              {annotations.map((a) => (
                <li key={a.table_annotation_uuid} className="annotationsModal__item">
                  <div className="annotationsModal__body">
                    <strong>
                      {a.schema_name}.{a.relation_name}
                    </strong>
                    <p>{a.body}</p>
                  </div>
                  <span className="annotationsModal__actions">
                    <button type="button" onClick={() => startEdit(a)}>편집</button>
                    <button
                      type="button"
                      onClick={() => onDelete(a.table_annotation_uuid)}
                      aria-label={`${a.schema_name}.${a.relation_name} 주석 삭제`}
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
