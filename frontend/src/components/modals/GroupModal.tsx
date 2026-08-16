import React from 'react';
import type { Node } from "@xyflow/react";
import type { TableNodeData } from "../../erd/convert";
import { BUSINESS_GROUP_COLORS, type BusinessGroup } from "../../erd/businessGroups";
import { useRef } from 'react';
import { useDialogAccessibility } from './useDialogAccessibility';

interface GroupModalProps {
  isOpen: boolean;
  businessGroups: BusinessGroup[];
  newGroupName: string;
  setNewGroupName: (name: string) => void;
  newGroupColor: string;
  setNewGroupColor: (color: string) => void;
  nodes: Node<TableNodeData>[];
  onCloseGroupManager: () => void;
  onCreateBusinessGroup: () => void;
  onDeleteBusinessGroup: (id: string) => void;
  onAssignBusinessGroup: (nodeId: string, groupId: string) => void;
}

export function GroupModal({
  isOpen,
  businessGroups,
  newGroupName,
  setNewGroupName,
  newGroupColor,
  setNewGroupColor,
  nodes,
  onCloseGroupManager,
  onCreateBusinessGroup,
  onDeleteBusinessGroup,
  onAssignBusinessGroup,
}: GroupModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onCloseGroupManager);
  const swatchesRef = useRef<HTMLDivElement>(null);

  if (!isOpen) return null;

  const handleSwatchKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, color: string, index: number) => {
    let nextIndex = index;

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextIndex = (index + 1) % BUSINESS_GROUP_COLORS.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextIndex = (index - 1 + BUSINESS_GROUP_COLORS.length) % BUSINESS_GROUP_COLORS.length;
    } else if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      setNewGroupColor(color);
      return;
    }

    if (nextIndex !== index) {
      const nextColor = BUSINESS_GROUP_COLORS[nextIndex];
      if (nextColor) {
        setNewGroupColor(nextColor);
        if (swatchesRef.current) {
          const swatches = Array.from(swatchesRef.current.querySelectorAll<HTMLButtonElement>('[role="radio"]'));
          swatches[nextIndex]?.focus();
        }
      }
    }
  };

  return (
    <div className="modalOverlay">
      <div
        className="modalContent groupManager"
        role="dialog"
        aria-modal="true"
        aria-labelledby="group-manager-title"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="modalHeader">
          <h3 id="group-manager-title">업무 그룹</h3>
          <button
            type="button"
            onClick={onCloseGroupManager}
            aria-label="업무 그룹 닫기"
          >
            닫기
          </button>
        </div>

        <form className="groupManager__create" onSubmit={(e) => { e.preventDefault(); if (newGroupName.trim()) { onCreateBusinessGroup(); } }}>
          <div className="field">
            <label htmlFor="business-group-name">그룹 이름</label>
            <input
              autoFocus
              id="business-group-name"
              value={newGroupName}
              onChange={(event) => setNewGroupName(event.target.value)}
              placeholder="Billing"
            />
          </div>
          <div
            className="groupManager__swatches"
            role="radiogroup"
            aria-label="그룹 색상"
            ref={swatchesRef}
          >
            {BUSINESS_GROUP_COLORS.map((color, index) => {
              const isChecked = newGroupColor === color;
              const hasChecked = BUSINESS_GROUP_COLORS.includes(newGroupColor as typeof BUSINESS_GROUP_COLORS[number]);
              const isFocusable = isChecked || (!hasChecked && index === 0);

              return (
                <button
                  type="button"
                  role="radio"
                  aria-label={`색상 ${color}`}
                  aria-checked={isChecked}
                  tabIndex={isFocusable ? 0 : -1}
                  className="groupManager__swatch"
                  key={color}
                  onClick={() => setNewGroupColor(color)}
                  onKeyDown={(e) => handleSwatchKeyDown(e, color, index)}
                  style={{ background: color }}
                />
              );
            })}
          </div>
          <button
            type="submit"
            disabled={!newGroupName.trim()}
          >
            추가
          </button>
        </form>

        <div className="groupManager__section">
          <h4>그룹</h4>
          {businessGroups.length === 0 ? (
            <div className="field-hint">등록된 그룹이 없습니다.</div>
          ) : (
            <div className="groupManager__list">
              {businessGroups.map((group) => (
                <div className="groupManager__group" key={group.id}>
                  <span
                    className="groupManager__dot"
                    style={{ background: group.color }}
                  />
                  <strong>{group.name}</strong>
                  <button
                    type="button"
                    aria-label={`${group.name} 그룹 삭제`}
                    onClick={() => {
                      if (!window.confirm("'" + group.name + "' 그룹을 삭제하시겠습니까?")) return;
                      onDeleteBusinessGroup(group.id);
                    }}
                  >
                    삭제
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="groupManager__section">
          <h4>테이블 배정</h4>
          <div className="groupManager__assignments">
            {nodes.map((node) => (
              <label className="groupManager__assignment" key={node.id}>
                <span
                  title={node.data.title}
                  aria-label={node.data.title}
                >
                  {node.data.title}
                </span>
                <select
                  aria-label={`${node.data.title} 그룹 배정`}
                  value={node.data.businessGroup?.id ?? ""}
                  onChange={(event) =>
                    onAssignBusinessGroup(node.id, event.target.value)
                  }
                >
                  <option value="">없음</option>
                  {businessGroups.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
