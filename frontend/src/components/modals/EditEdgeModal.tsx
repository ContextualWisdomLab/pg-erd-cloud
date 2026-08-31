import React from 'react';
import type { Edge } from "@xyflow/react";
import { RequiredIndicator } from './RequiredIndicator';
import { useDialogAccessibility } from './useDialogAccessibility';

interface EditEdgeModalProps {
  editingEdge: Edge | null;
  relLabel: string;
  setRelLabel: (label: string) => void;
  onRelDelete: () => void;
  onRelCancel: () => void;
  onRelSubmit: () => void;
}

/** Renders relationship editing and blocks blank constraint names before mutation. */
export function EditEdgeModal({
  editingEdge,
  relLabel,
  setRelLabel,
  onRelDelete,
  onRelCancel,
  onRelSubmit,
}: EditEdgeModalProps) {
  const dialogRef = useDialogAccessibility<HTMLFormElement>(Boolean(editingEdge), onRelCancel);
  const relLabelInputRef = React.useRef<HTMLInputElement>(null);

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
      <form
        className="modalContent"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-rel-title"
        ref={dialogRef}
        tabIndex={-1}
        onSubmit={(e) => {
          e.preventDefault();
          const input = relLabelInputRef.current;
          if (!relLabel.trim()) {
            input?.setCustomValidity("제약조건 이름을 입력하세요.");
            input?.reportValidity();
            return;
          }
          input?.setCustomValidity("");
          onRelSubmit();
        }}
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
          <label htmlFor="rel-label">
            제약조건 이름 (Label) <RequiredIndicator />
          </label>
          <input
            id="rel-label"
            ref={relLabelInputRef}
            value={relLabel}
            onInvalid={(e) => {
              if (!e.currentTarget.value.trim()) {
                e.currentTarget.setCustomValidity("제약조건 이름을 입력하세요.");
              }
            }}
            onChange={(e) => {
              e.currentTarget.setCustomValidity("");
              setRelLabel(e.target.value);
            }}
            placeholder="fk_constraint_name"
            autoFocus
            required
          />
        </div>
        <div
          className="row"
          style={{ justifyContent: "space-between", marginTop: 8 }}
        >
          <button
            type="button"
            onClick={() => {
              if (!window.confirm("이 관계를 삭제하시겠습니까?")) return;
              onRelDelete();
            }}
            style={{ color: "#b91c1c", borderColor: "#fca5a5" }}
          >
            삭제
          </button>
          <div className="row">
            <button type="button" onClick={onRelCancel}>취소</button>
            <button
              type="submit"
              style={{ background: "#034ea2", color: "#fff" }}
            >
              저장
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
