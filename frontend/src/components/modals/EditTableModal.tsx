import React from 'react';
import type { Node } from "@xyflow/react";
import type { TableNodeData } from "../../erd/convert";
import { ModalShell } from './ModalShell';

interface EditTableModalProps {
  isOpen: boolean;
  editingNode: Node<TableNodeData> | null;
  setEditingNode: React.Dispatch<React.SetStateAction<Node<TableNodeData> | null>>;
  setNodes: React.Dispatch<React.SetStateAction<Node<TableNodeData>[]>>;
  onEditTableCancel: () => void;
  onEditTableSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  onDeleteTable: () => void;
}

export function EditTableModal({
  isOpen,
  editingNode,
  setEditingNode,
  setNodes,
  onEditTableCancel,
  onEditTableSubmit,
  onDeleteTable,
}: EditTableModalProps) {
  if (!isOpen || !editingNode) return null;

  return (
    <ModalShell
      title="테이블 편집"
      titleId="edit-table-title"
      onClose={onEditTableCancel}
      closeLabel="닫기"
      size="editTable"
      footer={
        <div className="editTableModal__actions">
          <div className="row">
            <button
              type="button"
              onClick={onDeleteTable}
              className="buttonDanger"
              aria-label={`${editingNode.data.title} 테이블 삭제`}
            >
              테이블 삭제
            </button>
            <button
              type="button"
              aria-label={`${editingNode.data.title} 테이블 복제`}
              onClick={() => {
                const dupId = `${editingNode.id}_copy_${Date.now()}`;
                setNodes((nds) => [
                  ...nds,
                  {
                    ...editingNode,
                    id: dupId,
                    position: {
                      x: editingNode.position.x + 40,
                      y: editingNode.position.y + 40,
                    },
                    data: {
                      ...editingNode.data,
                      title: `${editingNode.data.title}_copy`,
                      columns: editingNode.data.columns.map((column) => ({ ...column })),
                    },
                  },
                ]);
                onEditTableCancel();
              }}
            >
              복제
            </button>
          </div>
          <div className="row">
            <button type="button" onClick={onEditTableCancel}>취소</button>
            <button
              type="submit"
              form="editTableForm"
              className="buttonPrimary"
            >
              저장
            </button>
          </div>
        </div>
      }
    >
          <form id="editTableForm" onSubmit={onEditTableSubmit} className="editTableForm">
            <div className="formStack">
              <label htmlFor="editTableTitle">테이블명 (schema.table)</label>
              <input
                id="editTableTitle"
                name="title"
                defaultValue={editingNode.data.title}
                placeholder="public.users"
                autoFocus
              />
            </div>
            <div className="formStack">
              <label htmlFor="editTableComment">코멘트 (선택)</label>
              <input
                id="editTableComment"
                name="comment"
                defaultValue={editingNode.data.comment || ""}
                placeholder="사용자 테이블"
              />
            </div>

            <div className="formStack editTableForm__columns">
              <div className="row editTableForm__columnsHeader">
                <h4>컬럼</h4>
                <button
                  type="button"
                  onClick={() => {
                    setNodes((nds: Node<TableNodeData>[]) =>
                      nds.map((n: Node<TableNodeData>) => {
                        if (n.id === editingNode.id) {
                          return {
                            ...n,
                            data: {
                              ...n.data,
                              columns: [
                                ...n.data.columns,
                                {
                                  column_name: `new_col_${Date.now()}`,
                                  data_type: "text",
                                  is_not_null: false,
                                  is_pk: false,
                                }
                              ]
                            }
                          };
                        }
                        return n;
                      })
                    );
                    setEditingNode((prev: Node<TableNodeData> | null) => {
                       if (!prev) return prev;
                       return {
                         ...prev,
                         data: {
                           ...prev.data,
                           columns: [
                             ...prev.data.columns,
                             {
                               column_name: `new_col_${Date.now()}`,
                               data_type: "text",
                               is_not_null: false,
                               is_pk: false,
                             }
                           ]
                         }
                       }
                    });
                  }}
                >
                  컬럼 추가
                </button>
              </div>

              <div className="formStack">
                {editingNode.data.columns.map((col, idx) => (
                  <div key={`${col.column_name}-${idx}`} className="editTableForm__columnRow">
                    <input
                      type="text"
                      name={`col_name_${idx}`}
                      defaultValue={col.column_name}
                      placeholder="컬럼명"
                      className="editTableForm__columnName"
                      aria-label={`${col.column_name} 컬럼명`}
                    />
                    <input
                      type="text"
                      name={`col_type_${idx}`}
                      defaultValue={col.data_type}
                      placeholder="데이터 타입"
                      className="editTableForm__columnType"
                      aria-label={`${col.column_name} 데이터 타입`}
                    />
                    <label className="row editTableForm__flag">
                      <input
                        type="checkbox"
                        name={`col_pk_${idx}`}
                        defaultChecked={col.is_pk}
                        aria-label={`${col.column_name} PK 설정`}
                      />
                      PK
                    </label>
                    <label className="row editTableForm__flag">
                      <input
                        type="checkbox"
                        name={`col_nn_${idx}`}
                        defaultChecked={col.is_not_null}
                        aria-label={`${col.column_name} NN 설정`}
                      />
                      NN
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        if (!window.confirm(`'${col.column_name}' 컬럼을 삭제하시겠습니까?`)) return;
                        setNodes((nds: Node<TableNodeData>[]) =>
                          nds.map((n: Node<TableNodeData>) => {
                            if (n.id === editingNode.id) {
                              return {
                                ...n,
                                data: {
                                  ...n.data,
                                  columns: n.data.columns.filter((_, i) => i !== idx)
                                }
                              };
                            }
                            return n;
                          })
                        );
                        setEditingNode((prev: Node<TableNodeData> | null) => {
                           if (!prev) return prev;
                           return {
                             ...prev,
                             data: {
                               ...prev.data,
                               columns: prev.data.columns.filter((_, i) => i !== idx)
                             }
                           };
                        });
                      }}
                      className="buttonDanger"
                      aria-label={`${col.column_name} 컬럼 삭제`}
                    >
                      삭제
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </form>
    </ModalShell>
  );
}
