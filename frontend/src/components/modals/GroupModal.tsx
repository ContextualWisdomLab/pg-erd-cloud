import React from 'react';
import type { Node } from "@xyflow/react";
import type { TableNodeData } from "../../erd/convert";
import { BUSINESS_GROUP_COLORS, type BusinessGroup } from "../../erd/businessGroups";
import { ModalShell } from './ModalShell';

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
  const selectedColorIndex = BUSINESS_GROUP_COLORS.indexOf(
    newGroupColor as (typeof BUSINESS_GROUP_COLORS)[number],
  );

  function onColorKeyDown(
    event: React.KeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ): void {
    const isNext = event.key === "ArrowRight" || event.key === "ArrowDown";
    const isPrevious = event.key === "ArrowLeft" || event.key === "ArrowUp";

    if (!isNext && !isPrevious) return;

    event.preventDefault();
    const direction = isNext ? 1 : -1;
    const nextIndex =
      (currentIndex + direction + BUSINESS_GROUP_COLORS.length) %
      BUSINESS_GROUP_COLORS.length;

    setNewGroupColor(BUSINESS_GROUP_COLORS[nextIndex]);
    event.currentTarget
      .closest<HTMLElement>('[role="radiogroup"]')
      ?.querySelectorAll<HTMLButtonElement>('[role="radio"]')
      [nextIndex]?.focus();
  }

  if (!isOpen) return null;

  return (
    <ModalShell
      title="업무 그룹"
      titleId="group-manager-title"
      onClose={onCloseGroupManager}
      closeLabel="업무 그룹 닫기"
      size="group"
    >

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
          >
            {BUSINESS_GROUP_COLORS.map((color, index) => (
              <button
                type="button"
                role="radio"
                aria-label={`색상 ${color}`}
                aria-checked={newGroupColor === color}
                className="groupManager__swatch"
                key={color}
                onClick={() => setNewGroupColor(color)}
                onKeyDown={(event) => onColorKeyDown(event, index)}
                style={{ background: color }}
                tabIndex={
                  newGroupColor === color ||
                  (selectedColorIndex === -1 && index === 0)
                    ? 0
                    : -1
                }
              />
            ))}
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
                    onClick={() => onDeleteBusinessGroup(group.id)}
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
    </ModalShell>
  );
}
