import React from 'react';
import type { Node } from "@xyflow/react";
import type { TableNodeData } from "../../erd/convert";
import { useDialogAccessibility } from './useDialogAccessibility';

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
  const dialogRef = useDialogAccessibility(isOpen && Boolean(editingNode), onEditTableCancel);

  if (!isOpen || !editingNode) return null;

  return (
    <div className="modalOverlay">
      <div className="modal" style={{ width: 800, maxWidth: "90vw", maxHeight: "90vh", display: "flex", flexDirection: "column" }} role="dialog" aria-modal="true" aria-labelledby="edit-table-title" ref={dialogRef} tabIndex={-1}>
        <div className="modal__header">
          <h3 id="edit-table-title">테이블 편집</h3>
          <button type="button" aria-label="닫기" onClick={onEditTableCancel}>X</button>
        </div>
        <div style={{ overflowY: "auto", padding: "0 4px", flex: 1 }}>
          <form id="editTableForm" onSubmit={onEditTableSubmit} className="col" style={{ gap: 12 }}>
            <div className="col">
              <label htmlFor="editTableTitle">테이블명 (schema.table)</label>
              <input
                id="editTableTitle"
                name="title"
                defaultValue={editingNode.data.title}
                placeholder="public.users"
                autoFocus
              />
            </div>
            <div className="col">
              <label htmlFor="editTableComment">코멘트 (선택)</label>
              <input
                id="editTableComment"
                name="comment"
                defaultValue={editingNode.data.comment || ""}
                placeholder="사용자 테이블"
              />
            </div>

            <div className="col" style={{ marginTop: 16 }}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <h4 style={{ margin: 0 }}>컬럼</h4>
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

              <div className="col" style={{ gap: 8 }}>
                {editingNode.data.columns.map((col, idx) => (
                  <div key={`${col.column_name}-${idx}`} className="row" style={{ gap: 8, alignItems: "center" }}>
                    <input
                      type="text"
                      name={`col_name_${idx}`}
                      defaultValue={col.column_name}
                      placeholder="컬럼명"
                      style={{ flex: 2 }}
                      aria-label={`${col.column_name} 컬럼명`}
                    />
                    <input
                      type="text"
                      name={`col_type_${idx}`}
                      defaultValue={col.data_type}
                      placeholder="데이터 타입"
                      style={{ flex: 1.5 }}
                      aria-label={`${col.column_name} 데이터 타입`}
                    />
                    <label className="row" style={{ gap: 4, whiteSpace: "nowrap" }}>
                      <input
                        type="checkbox"
                        name={`col_pk_${idx}`}
                        defaultChecked={col.is_pk}
                        aria-label={`${col.column_name} PK 여부`}
                      />
                      PK
                    </label>
                    <label className="row" style={{ gap: 4, whiteSpace: "nowrap" }}>
                      <input
                        type="checkbox"
                        name={`col_nn_${idx}`}
                        defaultChecked={col.is_not_null}
                        aria-label={`${col.column_name} NN 여부`}
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
                      style={{ color: "#b91c1c", padding: "4px 8px" }}
                      aria-label={`${col.column_name} 컬럼 삭제`}
                    >
                      삭제
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </form>
        </div>

        <div className="row" style={{ justifyContent: "space-between", marginTop: 16, paddingTop: 16, borderTop: "1px solid #e2e8f0" }}>
          <button
            type="button"
            onClick={onDeleteTable}
            style={{ color: "#b91c1c", borderColor: "#fca5a5" }}
          >
            테이블 삭제
          </button>
          <div className="row">
            <button type="button" onClick={onEditTableCancel}>취소</button>
            <button
              type="submit"
              form="editTableForm"
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
