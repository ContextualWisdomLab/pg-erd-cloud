import type { MigrationRun, MigrationRunState } from '../../types'

type RunStatusPanelProps = {
  run: MigrationRun
}

const STATE_LABELS: Record<MigrationRunState, string> = {
  queued: '대기 중',
  sandbox_running: '격리 환경에서 검증 중',
  live_preflight_running: '라이브 대상 읽기 전용 사전 점검 중',
  passed: '격리 검증 및 읽기 전용 사전 점검 통과',
  drifted: '기준 스키마 변경 감지',
  failed: '드라이런 실패',
  applying: '적용 중',
  reconciling: '적용 결과 조정 중',
  verifying: '적용 결과 검증 중',
  verified: '목표 스키마 수렴 검증 완료',
  drifted_no_apply: '변경 감지로 적용하지 않음',
  not_applied: '적용되지 않음이 확인됨',
  verification_failed: '적용 후 검증 실패',
  failed_rolled_back: '실패 후 전체 롤백 확인',
  applied_with_drift: '적용됐으나 목표와 불일치',
  outcome_unknown: '적용 결과 불명확',
}

const STATE_MEANINGS: Partial<Record<MigrationRunState, string>> = {
  passed: '라이브 대상에서 DDL을 실행했다는 의미가 아닙니다.',
  drifted: '기준 다이제스트가 달라 라이브 DDL을 실행하지 않았습니다.',
  failed: '드라이런 단계가 실패했으며 라이브 DDL을 실행하지 않았습니다.',
  verified: '저장된 검증 스냅샷이 목표 다이제스트와 일치합니다.',
  drifted_no_apply: '적용 전 변경이 감지되어 DDL을 실행하지 않았습니다.',
  not_applied: '조정 결과 기존 기준 다이제스트가 유지된 것으로 확인됐습니다.',
  verification_failed: '커밋은 알려졌지만 수렴 여부를 확인하지 못했습니다.',
  failed_rolled_back: '트랜잭션 세그먼트 전체가 롤백된 것으로 확인됐습니다.',
  applied_with_drift: '커밋 후 잔여 차이가 확인되어 성공으로 간주하지 않습니다.',
  outcome_unknown: '결과가 불명확하며 자동 재실행이 금지됩니다.',
}

function digestValue(value: string | null): string {
  return value ?? '없음'
}

export function RunStatusPanel({ run }: RunStatusPanelProps) {
  const stateMeaning = STATE_MEANINGS[run.state]

  return (
    <article className="forwardRunStatus">
      <header>
        <h2>마이그레이션 실행 상태</h2>
        <p
          role="status"
          aria-label="마이그레이션 실행 상태"
          aria-live="polite"
          aria-atomic="true"
        >
          {STATE_LABELS[run.state]}
        </p>
        {stateMeaning ? <p>{stateMeaning}</p> : null}
      </header>

      {run.cancellation_requested ? (
        <p role="alert" aria-label="취소 요청">
          취소 요청이 기록됐습니다. 다음 상태 전환 전까지 완료로 간주하지 않습니다.
        </p>
      ) : null}

      {run.error_code ? (
        <p role="alert" aria-label="실행 오류">
          오류 코드: <code>{run.error_code}</code>
        </p>
      ) : null}

      <section aria-label="실행 출처">
        <h3>실행 출처</h3>
        <dl>
          <div><dt>실행</dt><dd>{run.migration_run_uuid}</dd></div>
          <div><dt>종류</dt><dd>{run.run_kind}</dd></div>
          <div><dt>계획</dt><dd>{run.migration_plan_uuid}</dd></div>
          <div><dt>계획 다이제스트</dt><dd>{run.plan_digest}</dd></div>
          <div><dt>관측 기준 다이제스트</dt><dd>{digestValue(run.observed_base_digest)}</dd></div>
          <div><dt>상태 버전</dt><dd>{run.state_version}</dd></div>
          <div><dt>요청 시각</dt><dd><time dateTime={run.created_at}>{run.created_at}</time></dd></div>
          <div><dt>갱신 시각</dt><dd><time dateTime={run.updated_at}>{run.updated_at}</time></dd></div>
        </dl>
      </section>

      <section aria-label={`감사 이벤트 ${run.events.length}개`}>
        <h3>감사 이벤트</h3>
        <p>서버가 검증한 이벤트 메타데이터만 표시합니다.</p>
        <ol>
          {run.events.map((event) => (
            <li key={`${event.sequence_number}:${event.event_digest}`}>
              <h4>#{event.sequence_number} {event.event_type}</h4>
              <dl>
                <div>
                  <dt>상태 전환</dt>
                  <dd>{event.state_before ?? '없음'} → {event.state_after}</dd>
                </div>
                <div><dt>이벤트 다이제스트</dt><dd>{event.event_digest}</dd></div>
                <div>
                  <dt>이전 다이제스트</dt>
                  <dd>{digestValue(event.previous_event_digest)}</dd>
                </div>
                <div>
                  <dt>기록 시각</dt>
                  <dd><time dateTime={event.created_at}>{event.created_at}</time></dd>
                </div>
              </dl>
            </li>
          ))}
        </ol>
      </section>
    </article>
  )
}
