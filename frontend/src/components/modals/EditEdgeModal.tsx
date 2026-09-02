import React from 'react';
import type { Edge } from "@xyflow/react";
import { ModalShell } from './ModalShell';

interface EditEdgeModalProps {
  editingEdge: Edge | null;
  relLabel: string;
  setRelLabel: (label: string) => void;
  onRelDelete: () => void;
  onRelCancel: () => void;
  onRelSubmit: () => void;
}

export function EditEdgeModal({
  editingEdge,
  relLabel,
  setRelLabel,
  onRelDelete,
  onRelCancel,
  onRelSubmit,
}: EditEdgeModalProps) {
  if (!editingEdge) return null;

  return (
    <ModalShell
      title="관계 설정"
      titleId="edit-rel-title"
      onClose={onRelCancel}
      closeLabel="관계 설정 닫기"
      size="relationship"
      footer={
        <div className="relationshipModal__actions">
          <button
            type="button"
            className="buttonDanger"
            onClick={onRelDelete}
          >
            삭제
          </button>
          <div className="row">
            <button type="button" onClick={onRelCancel}>취소</button>
            <button
              type="submit"
              form="relationship-form"
              className="buttonPrimary"
            >
              저장
            </button>
          </div>
        </div>
      }
    >
      <form
        id="relationship-form"
        onSubmit={(e) => {
          e.preventDefault();
          onRelSubmit();
        }}
      >
        <div className="relationshipModal__endpoints">
          From: {editingEdge.source} <br />
          To: {editingEdge.target}
        </div>
        <div className="field">
          <label htmlFor="rel-label">제약조건 이름 (Label)</label>
          <input
            id="rel-label"
            value={relLabel}
            onChange={(e) => setRelLabel(e.target.value)}
            placeholder="fk_constraint_name"
            autoFocus
          />
        </div>
      </form>
    </ModalShell>
  );
}
