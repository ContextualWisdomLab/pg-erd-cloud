import React from 'react';

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
      <div
        className="modalContent"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-table-title"
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
          />
        </div>
        <div
          className="row"
          style={{ justifyContent: "flex-end", marginTop: 8 }}
        >
          <button onClick={onAddTableCancel}>취소</button>
          <button
            onClick={onAddTableSubmit}
            style={{ background: "#034ea2", color: "#fff" }}
          >
            저장
          </button>
        </div>
      </div>
    </div>
  );
}
