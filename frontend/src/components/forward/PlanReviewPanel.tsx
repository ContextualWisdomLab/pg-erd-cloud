import type {
  MigrationPlan,
  MigrationPlanObjectRef,
  MigrationPlanStatement,
} from '../../types'

type PlanReviewPanelProps = {
  plan: MigrationPlan
}

function objectRefLabel(objectRef: MigrationPlanObjectRef): string {
  return [
    objectRef.database,
    objectRef.schema_name,
    objectRef.table_name,
    objectRef.column_name,
  ].filter(Boolean).join('.')
}

function StatementList({ statements }: { statements: ReadonlyArray<MigrationPlanStatement> }) {
  if (statements.length === 0) return null

  return (
    <ol className="forwardPlanReview__statementList">
      {statements.map((statement, index) => (
        <li key={`${statement.kind}:${statement.target}:${index}`}>
          <header>
            <strong>{statement.kind}</strong>
            <span>{statement.target}</span>
          </header>
          <dl>
            <div><dt>위험</dt><dd>{statement.risk.severity}</dd></div>
            <div><dt>잠금</dt><dd>{statement.risk.lock_mode}</dd></div>
            <div><dt>트랜잭션</dt><dd>{statement.transactional ? '예' : '아니요'}</dd></div>
            <div><dt>되돌리기</dt><dd>{statement.reversible ? '가능' : '불가'}</dd></div>
            <div><dt>객체 참조</dt><dd>{objectRefLabel(statement.object_ref)}</dd></div>
            <div><dt>의존성</dt><dd>{statement.dependencies.join(', ')}</dd></div>
            <div>
              <dt>의존 객체</dt>
              <dd>{statement.dependency_refs.map(objectRefLabel).join(', ')}</dd>
            </div>
            <div><dt>필요 권한</dt><dd>{statement.required_privileges.join(', ')}</dd></div>
            <div>
              <dt>사전 조건</dt>
              <dd>{statement.preconditions.map((value) => JSON.stringify(value)).join(', ')}</dd>
            </div>
          </dl>
          <p>{statement.risk.detail}</p>
          <pre><code>{statement.sql}</code></pre>
        </li>
      ))}
    </ol>
  )
}

export function PlanReviewPanel({ plan }: PlanReviewPanelProps) {
  return (
    <article className="forwardPlanReview">
      <header>
        <h2>마이그레이션 계획 검토</h2>
        <p>서버가 컴파일한 불변 계획입니다. 이 화면은 SQL 실행 권한을 갖지 않습니다.</p>
      </header>

      <section aria-label="계획 출처">
        <h3>계획 출처</h3>
        <dl>
          <div><dt>계획</dt><dd>{plan.migration_plan_uuid}</dd></div>
          <div><dt>모델 리비전</dt><dd>{plan.schema_model_revision_uuid}</dd></div>
          <div><dt>기준 스냅샷</dt><dd>{plan.base_schema_snapshot_uuid}</dd></div>
          <div><dt>대상 연결</dt><dd>{plan.db_connection_uuid}</dd></div>
          <div><dt>호환 버전</dt><dd>PostgreSQL {plan.postgresql_major}</dd></div>
          <div><dt>컴파일러</dt><dd>{plan.compiler_version}</dd></div>
          <div><dt>계획 다이제스트</dt><dd>{plan.plan_digest}</dd></div>
          <div><dt>만료</dt><dd><time dateTime={plan.expires_at}>{plan.expires_at}</time></dd></div>
        </dl>
      </section>

      <section aria-label="위험 요약">
        <h3>위험 요약</h3>
        <ul>
          <li>안전 {plan.risk_summary.safe}</li>
          <li>경고 {plan.risk_summary.warning}</li>
          <li>파괴적 {plan.risk_summary.destructive}</li>
        </ul>
      </section>

      {plan.blockers.length > 0 ? (
        <section role="alert" aria-label="계획 차단 사유">
          <h3>계획 차단 사유</h3>
          <ul>
            {plan.blockers.map((blocker, index) => (
              <li key={`${blocker.code}:${blocker.object}:${index}`}>
                <strong>{blocker.code}</strong>: {blocker.object} — {blocker.detail}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-label={`실행 가능한 문 ${plan.statements.length}개`}>
        {plan.statements.length > 0 ? <h3>실행 가능한 문</h3> : null}
        <StatementList statements={plan.statements} />
      </section>

      {plan.proposed_statements.length > 0 ? (
        <section aria-label={`검토 전용 제안 ${plan.proposed_statements.length}개`}>
          <h3>검토 전용 제안</h3>
          <p>차단 사유가 있어 이 SQL에는 실행 권한이 없습니다.</p>
          <StatementList statements={plan.proposed_statements} />
        </section>
      ) : null}
    </article>
  )
}
