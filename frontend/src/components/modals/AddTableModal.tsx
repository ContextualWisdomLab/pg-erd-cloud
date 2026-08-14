import React from 'react';
import { useDialogAccessibility } from './useDialogAccessibility';

interface AddTableModalProps {
  isOpen: boolean;
  newTableName: string;
  setNewTableName: (name: string) => void;
  onAddTableCancel: () => void;
  onAddTableSubmit: () => void;
}

export function AddTableModal({
  isOpen,
  newTableName,
  setNewTableName,
  onAddTableCancel,
  onAddTableSubmit,
}: AddTableModalProps) {
  const dialogRef = useDialogAccessibility<HTMLFormElement>(isOpen, onAddTableCancel);

  if (!isOpen) return null;

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
        aria-labelledby="add-table-title"
        ref={dialogRef}
        tabIndex={-1}
        onSubmit={(e) => {
          e.preventDefault();
          if (newTableName.trim()) {
            onAddTableSubmit();
          }
        }}
        style={{
          background: "#fff",
          padding: 20,
          borderRadius: 8,
          width: 300,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <h3 id="add-table-title">테이블 추가</h3>
        <div className="field">
          <label htmlFor="new-table-name">테이블 이름</label>
          <input
            id="new-table-name"
            value={newTableName}
            onChange={(e) => setNewTableName(e.target.value)}
            placeholder="users"
            autoFocus
            required
          />
        </div>
        <div
          className="row"
          style={{ justifyContent: "flex-end", marginTop: 8 }}
        >
          <button type="button" onClick={onAddTableCancel}>취소</button>
          <button
            type="submit"
            disabled={!newTableName.trim()}
            style={
              newTableName.trim()
                ? { background: "#034ea2", color: "#fff" }
                : undefined
            }
          >
            저장
          </button>
        </div>
      </form>
    </div>
  );
}
