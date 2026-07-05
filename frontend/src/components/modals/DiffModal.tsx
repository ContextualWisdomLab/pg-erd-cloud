import React from 'react';
import type { SchemaDiff, Snapshot } from '../../types';
import { useDialogAccessibility } from './useDialogAccessibility';

interface DiffModalProps {
  isOpen: boolean;
  /** Short label for the snapshot being viewed (the diff target). */
  targetLabel: string;
  /** Snapshots that can be chosen as the comparison base (target excluded). */
  baseCandidates: Snapshot[];
  selectedBaseId: string | null;
  diff: SchemaDiff | null;
  isLoading: boolean;
  error: string | null;
  /** True when the API returned status="not_found" (missing/unauthorized). */
  notFound: boolean;
  onSelectBase: (baseSnapshotId: string) => void;
  onClose: () => void;
}

function shortId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

export function DiffModal({
  isOpen,
  targetLabel,
  baseCandidates,
  selectedBaseId,
  diff,
  isLoading,
  error,
  notFound,
  onSelectBase,
  onClose,
}: DiffModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onClose);

  if (!isOpen) return null;

  const summary = diff?.summary;

  return (
    <div className="modalOverlay">
      <div
        className="modalContent diffModal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="schema-diff-title"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="modalHeader">
          <div>
            <h3 id="schema-diff-title">스키마 비교</h3>
            <p className="modalLead">
              현재 스냅샷({targetLabel})을 이전 스냅샷과 비교해 변경 사항을 확인합니다.
            </p>
          </div>
          <button type="button" onClick={onClose}>닫기</button>
        </div>

        <section className="diffModal__controls">
          <label htmlFor="diff-base-select">비교 기준 스냅샷</label>
          <select
            id="diff-base-select"
            value={selectedBaseId ?? ''}
            onChange={(e) => onSelectBase(e.target.value)}
          >
            <option value="" disabled>
              기준 스냅샷 선택
            </option>
            {baseCandidates.map((s) => (
              <option key={s.schema_snapshot_uuid} value={s.schema_snapshot_uuid}>
                {shortId(s.schema_snapshot_uuid)}
                {s.schema_filter ? ` · ${s.schema_filter}` : ''}
              </option>
            ))}
          </select>
        </section>

        {isLoading ? (
          <span className="field-hint" role="status">비교 중…</span>
        ) : null}

        {error ? (
          <div className="error" role="alert">{error}</div>
        ) : null}

        {notFound ? (
          <span className="field-hint">
            스냅샷을 찾을 수 없거나 접근 권한이 없습니다.
          </span>
        ) : null}

        {!isLoading && !error && !notFound && !selectedBaseId ? (
          <span className="field-hint">비교할 기준 스냅샷을 선택하세요.</span>
        ) : null}

        {diff && summary ? (
          <>
            <section className="diffModal__summary" aria-label="변경 요약">
              {!summary.has_changes ? (
                <span className="statusPill statusPill--succeeded">변경 없음</span>
              ) : (
                <ul className="diffModal__summaryList">
                  <li>테이블 +{summary.tables_added} / -{summary.tables_removed} / 변경 {summary.tables_changed}</li>
                  <li>컬럼 +{summary.columns_added} / -{summary.columns_removed} / 변경 {summary.columns_changed}</li>
                  <li>외래키 +{summary.fks_added} / -{summary.fks_removed}</li>
                </ul>
              )}
            </section>

            {diff.tables.added.length > 0 ? (
              <section className="diffModal__section" aria-labelledby="diff-added-title">
                <h4 id="diff-added-title">추가된 테이블</h4>
                <ul>
                  {diff.tables.added.map((t) => (
                    <li key={t} className="diffModal__added">+ {t}</li>
                  ))}
                </ul>
              </section>
            ) : null}

            {diff.tables.removed.length > 0 ? (
              <section className="diffModal__section" aria-labelledby="diff-removed-title">
                <h4 id="diff-removed-title">삭제된 테이블</h4>
                <ul>
                  {diff.tables.removed.map((t) => (
                    <li key={t} className="diffModal__removed">- {t}</li>
                  ))}
                </ul>
              </section>
            ) : null}

            {diff.tables.changed.length > 0 ? (
              <section className="diffModal__section" aria-labelledby="diff-changed-title">
                <h4 id="diff-changed-title">변경된 테이블</h4>
                {diff.tables.changed.map((t) => (
                  <div key={t.table} className="diffModal__changedTable">
                    <strong>{t.table}</strong>
                    {t.primary_key ? (
                      <div className="diffModal__pk">
                        PK: {t.primary_key.from.join(', ') || '—'} → {t.primary_key.to.join(', ') || '—'}
                      </div>
                    ) : null}
                    {t.columns.added.map((c) => (
                      <div key={`a-${c}`} className="diffModal__added">+ 컬럼 {c}</div>
                    ))}
                    {t.columns.removed.map((c) => (
                      <div key={`r-${c}`} className="diffModal__removed">- 컬럼 {c}</div>
                    ))}
                    {t.columns.changed.map((c) => (
                      <div key={`c-${c.column}`} className="diffModal__changed">
                        ~ {c.column}: {c.from.data_type ?? '?'}
                        {c.from.is_not_null ? ' NOT NULL' : ''} → {c.to.data_type ?? '?'}
                        {c.to.is_not_null ? ' NOT NULL' : ''}
                      </div>
                    ))}
                  </div>
                ))}
              </section>
            ) : null}

            {diff.foreign_keys.added.length > 0 || diff.foreign_keys.removed.length > 0 ? (
              <section className="diffModal__section" aria-labelledby="diff-fk-title">
                <h4 id="diff-fk-title">외래키 변경</h4>
                {diff.foreign_keys.added.map((fk, i) => (
                  <div key={`fka-${i}`} className="diffModal__added">
                    + {fk.child_table}({fk.child_columns.join(', ')}) → {fk.parent_table}({fk.parent_columns.join(', ')})
                  </div>
                ))}
                {diff.foreign_keys.removed.map((fk, i) => (
                  <div key={`fkr-${i}`} className="diffModal__removed">
                    - {fk.child_table}({fk.child_columns.join(', ')}) → {fk.parent_table}({fk.parent_columns.join(', ')})
                  </div>
                ))}
              </section>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
