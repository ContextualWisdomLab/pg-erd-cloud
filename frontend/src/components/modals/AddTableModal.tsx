import React from 'react';
import { ModalShell } from './ModalShell';

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
  const isNameMissing = !newTableName.trim();

  const submitIfValid = () => {
    if (!isNameMissing) {
      onAddTableSubmit();
    }
  };

  return (
    <ModalShell
      title="테이블 추가"
      titleId="add-table-title"
      onClose={onAddTableCancel}
      closeLabel="테이블 추가 닫기"
      size="addTable"
      footer={
        <>
          <button type="button" onClick={onAddTableCancel}>취소</button>
          <button
            type="submit"
            form="add-table-form"
            className="buttonPrimary"
            aria-disabled={isNameMissing}
            aria-describedby="add-table-prerequisite"
          >
            저장
          </button>
        </>
      }
    >
      <form
        id="add-table-form"
        onSubmit={(e) => {
          e.preventDefault();
          submitIfValid();
        }}
      >
        <div className="field">
          <label htmlFor="new-table-name">테이블 이름</label>
          <input
            id="new-table-name"
            value={newTableName}
            onChange={(e) => setNewTableName(e.target.value)}
            placeholder="users"
            autoFocus
            required
            aria-describedby="add-table-prerequisite"
          />
          <span id="add-table-prerequisite" className="srOnly">
            테이블 이름을 입력하면 저장할 수 있습니다.
          </span>
        </div>
      </form>
    </ModalShell>
  );
}
