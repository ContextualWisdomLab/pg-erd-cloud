import React from 'react';
import type { Edge } from "@xyflow/react";
import { useDialogAccessibility } from './useDialogAccessibility';

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
  const dialogRef = useDialogAccessibility(Boolean(editingEdge), onRelCancel);

  if (!editingEdge) return null;

  return (
    <div
      className="modalOverlay"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.5)",
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        className="modalContent"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-rel-title"
        ref={dialogRef}
        tabIndex={-1}
        style={{
          background: "#fff",
          padding: 20,
          borderRadius: 8,
          width: 320,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <h3 id="edit-rel-title">관계 설정</h3>
        <div style={{ fontSize: 13, color: "#4b5563" }}>
          From: {editingEdge.source} <br />
          To: {editingEdge.target}
        </div>
        <div className="field">
          <label htmlFor="rel-label">제약조건 이름 (Label)</label>
          <input
            id="rel-label"
            value={relLabel}
            onChange={(e) => setRelLabel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                onRelSubmit();
              }
            }}
            placeholder="fk_constraint_name"
            autoFocus
          />
        </div>
        <div
          className="row"
          style={{ justifyContent: "space-between", marginTop: 8 }}
        >
          <button
            type="button"
            onClick={() => {
              if (window.confirm("이 관계를 삭제하시겠습니까?")) {
                onRelDelete();
              }
            }}
            style={{ color: "#b91c1c", borderColor: "#fca5a5" }}
            aria-label="관계 삭제"
          >
            삭제
          </button>
          <div className="row">
            <button type="button" onClick={onRelCancel}>취소</button>
            <button
              type="button"
              onClick={onRelSubmit}
              style={{ background: "#034ea2", color: "#fff" }}
            >
              저장
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
