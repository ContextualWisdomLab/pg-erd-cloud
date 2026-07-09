import React from 'react';
import type { Node } from "@xyflow/react";
import type { TableNodeData } from "../../erd/convert";
import type { IndexRecommendation } from "../../erd/cardinality";
import { useDialogAccessibility } from './useDialogAccessibility';

interface CardinalityModalProps {
  isOpen: boolean;
  cardinalityNode: Node<TableNodeData> | null;
  nodes: Node<TableNodeData>[];
  cardinalityRowCount: string;
  setCardinalityRowCount: (count: string) => void;
  cardinalityRowCountNumber: number | null;
  cardinalityDistinctCounts: Record<string, string>;
  cardinalityColumnSelections: Record<string, boolean>;
  cardinalityRecommendations: IndexRecommendation[];
  appliedCardinalitySignatures: { names: Set<string>; columns: Set<string> };
  onCloseCardinalityWizard: () => void;
  onCardinalityTableChange: (nodeId: string) => void;
  onCardinalityColumnToggle: (columnName: string, isChecked: boolean) => void;
  onCardinalityDistinctCountChange: (columnName: string, value: string) => void;
  onApplyCardinalityRecommendation: (recommendation: IndexRecommendation) => void;
  parsePositiveInteger: (value: string) => number | null;
  calculateCardinalityRatio: (rowCount: number, distinctCount: number) => number;
  formatPercent: (value: number) => string;
  strengthLabel: (strength: any) => string;
}

export function CardinalityModal({
  isOpen,
  cardinalityNode,
  nodes,
  cardinalityRowCount,
  setCardinalityRowCount,
  cardinalityRowCountNumber,
  cardinalityDistinctCounts,
  cardinalityColumnSelections,
  cardinalityRecommendations,
  appliedCardinalitySignatures,
  onCloseCardinalityWizard,
  onCardinalityTableChange,
  onCardinalityColumnToggle,
  onCardinalityDistinctCountChange,
  onApplyCardinalityRecommendation,
  parsePositiveInteger,
  calculateCardinalityRatio,
  formatPercent,
  strengthLabel,
}: CardinalityModalProps) {
  const dialogRef = useDialogAccessibility(isOpen && Boolean(cardinalityNode), onCloseCardinalityWizard);

  if (!isOpen || !cardinalityNode) return null;

  return (
    <div className="modalOverlay">
      <div
        className="modalContent cardinalityWizard"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cardinality-title"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="modalHeader">
          <h3 id="cardinality-title">인덱스 카디널리티</h3>
          <button
            type="button"
            onClick={onCloseCardinalityWizard}
            aria-label="카디널리티 계산 닫기"
          >
            닫기
          </button>
        </div>

        <div className="cardinalityWizard__controls">
          <div className="field">
            <label htmlFor="cardinality-table">테이블</label>
            <select
              autoFocus
              id="cardinality-table"
              value={cardinalityNode.id}
              onChange={(event) =>
                onCardinalityTableChange(event.target.value)
              }
            >
              {nodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.data.title}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="cardinality-row-count">행 수</label>
            <input
              id="cardinality-row-count"
              inputMode="numeric"
              min="1"
              type="number"
              value={cardinalityRowCount}
              onChange={(event) => {
                const value = event.target.value;
                if (/^\d*$/.test(value)) {
                  setCardinalityRowCount(value);
                }
              }}
            />
          </div>
        </div>

        <div className="cardinalityWizard__columns">
          <table>
            <thead>
              <tr>
                <th scope="col">사용</th>
                <th scope="col">컬럼</th>
                <th scope="col">Distinct</th>
                <th scope="col">비율</th>
              </tr>
            </thead>
            <tbody>
              {cardinalityNode.data.columns.map((column, index) => {
                const distinctCount = parsePositiveInteger(
                  cardinalityDistinctCounts[column.column_name] ?? "",
                );
                const ratio =
                  cardinalityRowCountNumber !== null &&
                  distinctCount !== null
                    ? calculateCardinalityRatio(
                        cardinalityRowCountNumber,
                        distinctCount,
                      )
                    : null;
                const inputId = `cardinality-${index}`;
                return (
                  <tr key={column.column_name}>
                    <td>
                      <input
                        aria-label={`${column.column_name} 사용`}
                        checked={
                          cardinalityColumnSelections[
                            column.column_name
                          ] ?? false
                        }
                        onChange={(event) =>
                          onCardinalityColumnToggle(
                            column.column_name,
                            event.target.checked,
                          )
                        }
                        type="checkbox"
                      />
                    </td>
                    <td>
                      <span className="cardinalityWizard__columnIdentity">
                        <label htmlFor={inputId}>
                          {column.column_name}
                        </label>
                        <span>{column.data_type}</span>
                      </span>
                    </td>
                    <td>
                      <input
                        id={inputId}
                        aria-label={`${index + 1}번째 컬럼 고유 값(Distinct) 수`}
                        inputMode="numeric"
                        min="1"
                        type="number"
                        value={
                          cardinalityDistinctCounts[
                            column.column_name
                          ] ?? ""
                        }
                        onChange={(event) =>
                          onCardinalityDistinctCountChange(
                            column.column_name,
                            event.target.value,
                          )
                        }
                      />
                    </td>
                    <td>{ratio === null ? "—" : formatPercent(ratio)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="cardinalityWizard__recommendations">
          <h4>추천 결과</h4>
          {cardinalityRowCountNumber === null ? (
            <div className="field-hint">Rows 값을 입력하세요.</div>
          ) : null}
          {cardinalityRowCountNumber !== null &&
          cardinalityRecommendations.length === 0 ? (
            <div className="field-hint">
              사용할 컬럼과 distinct 값을 선택하세요.
            </div>
          ) : null}
          {cardinalityRecommendations.map((recommendation) => {
            const isApplied =
              (recommendation.index_name && appliedCardinalitySignatures.names.has(recommendation.index_name)) ||
              (recommendation.columns && recommendation.columns.length > 0 && appliedCardinalitySignatures.columns.has(recommendation.columns.join(",")));
            return (
              <div
                className={`cardinalityRecommendation cardinalityRecommendation--${recommendation.strength}`}
                key={`${recommendation.index_name}-${recommendation.columns.join("-")}`}
              >
                <div>
                  <div className="cardinalityRecommendation__title">
                    <span>{strengthLabel(recommendation.strength)}</span>
                    <strong>{recommendation.index_name}</strong>
                  </div>
                  <div className="field-hint">
                    {recommendation.columns.join(", ")} ·{" "}
                    {formatPercent(recommendation.cardinality_ratio)} ·{" "}
                    {recommendation.reason}
                  </div>
                </div>
                <button
                  type="button"
                  disabled={
                    recommendation.strength === "skip" || isApplied
                  }
                  onClick={() =>
                    onApplyCardinalityRecommendation(recommendation)
                  }
                >
                  {isApplied ? "적용됨" : "적용"}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
