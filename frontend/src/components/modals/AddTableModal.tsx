import React from 'react'
import { useDialogAccessibility } from './useDialogAccessibility'

interface AddTableModalProps {
  isOpen: boolean
  newTableName: string
  setNewTableName: (name: string) => void
  onAddTableCancel: () => void
  onAddTableSubmit: () => void
}

const SAVE_HELP_ID = 'add-table-save-help'

export function AddTableModal({
  isOpen,
  newTableName,
  setNewTableName,
  onAddTableCancel,
  onAddTableSubmit,
}: AddTableModalProps) {
  const dialogRef = useDialogAccessibility<HTMLFormElement>(
    isOpen,
    onAddTableCancel,
  )
  const canSubmit = newTableName.trim().length > 0

  if (!isOpen) return null

  return (
    <div
      className="modalOverlay"
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.5)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <form
        className="modalContent"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-table-title"
        ref={dialogRef}
        tabIndex={-1}
        onSubmit={(event) => {
          event.preventDefault()
          if (canSubmit) {
            onAddTableSubmit()
          }
        }}
        style={{
          background: '#fff',
          padding: 20,
          borderRadius: 8,
          width: 300,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <h3 id="add-table-title">테이블 추가</h3>
        <div className="field">
          <label htmlFor="new-table-name">테이블 이름</label>
          <input
            id="new-table-name"
            value={newTableName}
            onChange={(event) => setNewTableName(event.target.value)}
            placeholder="users"
            autoFocus
            required
            aria-describedby={!canSubmit ? SAVE_HELP_ID : undefined}
          />
          {!canSubmit ? (
            <span id={SAVE_HELP_ID}>테이블 이름을 입력하면 저장할 수 있습니다.</span>
          ) : null}
        </div>
        <div
          className="row"
          style={{ justifyContent: 'flex-end', marginTop: 8 }}
        >
          <button type="button" onClick={onAddTableCancel}>
            취소
          </button>
          <button
            type="submit"
            aria-disabled={!canSubmit}
            aria-describedby={!canSubmit ? SAVE_HELP_ID : undefined}
            onClick={(event) => {
              if (!canSubmit) event.preventDefault()
            }}
            style={
              canSubmit
                ? { background: '#034ea2', color: '#fff' }
                : { opacity: 0.5, cursor: 'not-allowed' }
            }
          >
            저장
          </button>
        </div>
      </form>
    </div>
  )
}
