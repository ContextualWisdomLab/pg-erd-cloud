import { type FormEvent, useEffect, useRef, useState } from 'react'

import { createApplyRun } from '../../api'
import type { MigrationPlan, MigrationRun, MigrationRunAction } from '../../types'

type ApplyIntentPanelProps = {
  plan: MigrationPlan
  passedDryRun: MigrationRun
  onRunCreated: (runId: string) => void
}

type RequestState =
  | { status: 'idle' }
  | { status: 'requesting' }
  | { status: 'error' }
  | { status: 'created'; action: MigrationRunAction }

function isExactPassedDryRun(plan: MigrationPlan, run: MigrationRun): boolean {
  return run.run_kind === 'dry_run'
    && run.state === 'passed'
    && run.migration_plan_uuid === plan.migration_plan_uuid
    && run.plan_digest === plan.plan_digest
    && run.observed_base_digest === plan.base_digest
}

export function ApplyIntentPanel({
  plan,
  passedDryRun,
  onRunCreated,
}: ApplyIntentPanelProps) {
  const [targetConnectionName, setTargetConnectionName] = useState('')
  const [destructiveAcknowledged, setDestructiveAcknowledged] = useState(false)
  const [requestState, setRequestState] = useState<RequestState>({ status: 'idle' })
  const requestKeyRef = useRef<string | null>(null)
  const submittedTargetNameRef = useRef<string | null>(null)
  const submittedAcknowledgementRef = useRef<boolean | null>(null)
  const inFlightRef = useRef(false)
  const generationRef = useRef(0)

  useEffect(() => {
    generationRef.current += 1
    requestKeyRef.current = null
    submittedTargetNameRef.current = null
    submittedAcknowledgementRef.current = null
    inFlightRef.current = false
    setTargetConnectionName('')
    setDestructiveAcknowledged(false)
    setRequestState({ status: 'idle' })

    return () => {
      generationRef.current += 1
      inFlightRef.current = false
    }
  }, [
    passedDryRun.migration_run_uuid,
    passedDryRun.state_version,
    plan.migration_plan_uuid,
    plan.plan_digest,
  ])

  if (!isExactPassedDryRun(plan, passedDryRun)) {
    return (
      <section className="forwardApplyIntent" aria-label="비실행 apply 의도">
        <h3>Apply 검토</h3>
        <p>apply 의도를 등록할 수 없습니다.</p>
      </section>
    )
  }

  const submit = async () => {
    if (
      inFlightRef.current
      || targetConnectionName.length === 0
      || (plan.requires_destructive_confirmation && !destructiveAcknowledged)
    ) return

    inFlightRef.current = true
    const generation = generationRef.current
    setRequestState({ status: 'requesting' })

    try {
      const requestKey = requestKeyRef.current
        ?? `web-apply-intent-${globalThis.crypto.randomUUID()}`
      requestKeyRef.current = requestKey
      submittedTargetNameRef.current ??= targetConnectionName
      submittedAcknowledgementRef.current ??= plan.requires_destructive_confirmation
        ? destructiveAcknowledged
        : false
      const action = await createApplyRun(
        plan.migration_plan_uuid,
        {
          plan_digest: plan.plan_digest,
          passed_dry_run_uuid: passedDryRun.migration_run_uuid,
          target_connection_name: submittedTargetNameRef.current,
          destructive_acknowledged: submittedAcknowledgementRef.current,
        },
        requestKey,
      )
      if (generation !== generationRef.current) return
      setRequestState({ status: 'created', action })
      onRunCreated(action.migration_run_uuid)
    } catch {
      if (generation === generationRef.current) setRequestState({ status: 'error' })
    } finally {
      if (generation === generationRef.current) inFlightRef.current = false
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void submit()
  }

  const submitDisabled = requestState.status === 'requesting'
    || targetConnectionName.length === 0
    || (plan.requires_destructive_confirmation && !destructiveAcknowledged)
  const confirmationLocked = requestKeyRef.current !== null

  return (
    <section className="forwardApplyIntent" aria-label="비실행 apply 의도">
      <h3>Apply 검토</h3>
      <p>
        이 단계는 검토 증거와 대상 이름을 서버에 묶어 비실행 apply 의도만 등록합니다.
        실제 DDL을 디스패치하거나 실행하지 않습니다.
      </p>
      <form onSubmit={handleSubmit}>
        <label>
          대상 연결 이름 확인
          <input
            type="text"
            value={targetConnectionName}
            maxLength={128}
            required
            disabled={confirmationLocked}
            onChange={(event) => setTargetConnectionName(event.target.value)}
          />
        </label>
        {plan.requires_destructive_confirmation ? (
          <label>
            <input
              type="checkbox"
              checked={destructiveAcknowledged}
              disabled={confirmationLocked}
              onChange={(event) => setDestructiveAcknowledged(event.target.checked)}
            />
            파괴적 변경을 검토하고 확인했습니다.
          </label>
        ) : null}

        {requestState.status === 'created' ? (
          <p role="status" aria-live="polite">
            {requestState.action.reused ? '기존 등록을 재사용했습니다.' : '의도를 등록했습니다.'}
            {' '}실행 {requestState.action.migration_run_uuid}
          </p>
        ) : null}

        {requestState.status === 'error' ? (
          <div role="alert">
            <p>등록 결과를 확인하지 못했습니다. 같은 등록을 안전하게 다시 확인할 수 있습니다.</p>
            <button type="button" onClick={() => void submit()}>
              같은 등록 다시 시도
            </button>
          </div>
        ) : null}

        {requestState.status === 'idle' || requestState.status === 'requesting' ? (
          <button type="submit" disabled={submitDisabled}>
            {requestState.status === 'requesting'
              ? '등록 중…'
              : '비실행 apply 의도 등록'}
          </button>
        ) : null}
      </form>
    </section>
  )
}
