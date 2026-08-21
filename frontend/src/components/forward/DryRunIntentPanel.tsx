import { useEffect, useRef, useState } from 'react'

import { createDryRun } from '../../api'
import type { MigrationPlan, MigrationRunAction } from '../../types'

type DryRunIntentPanelProps = {
  plan: MigrationPlan
  onRunCreated: (runId: string) => void
}

type RequestState =
  | { status: 'idle' }
  | { status: 'requesting' }
  | { status: 'error' }
  | { status: 'created'; action: MigrationRunAction }

export function DryRunIntentPanel({ plan, onRunCreated }: DryRunIntentPanelProps) {
  const [requestState, setRequestState] = useState<RequestState>({ status: 'idle' })
  const requestKeyRef = useRef<string | null>(null)
  const inFlightRef = useRef(false)
  const generationRef = useRef(0)

  useEffect(() => {
    generationRef.current += 1
    requestKeyRef.current = null
    inFlightRef.current = false
    setRequestState({ status: 'idle' })

    return () => {
      generationRef.current += 1
      inFlightRef.current = false
    }
  }, [plan.migration_plan_uuid, plan.plan_digest])

  const submit = async () => {
    if (inFlightRef.current) return
    inFlightRef.current = true
    const generation = generationRef.current
    setRequestState({ status: 'requesting' })

    try {
      const requestKey = requestKeyRef.current
        ?? `web-dry-run-${globalThis.crypto.randomUUID()}`
      requestKeyRef.current = requestKey
      const action = await createDryRun(
        plan.migration_plan_uuid,
        plan.plan_digest,
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

  if (!plan.can_dry_run || plan.blockers.length > 0) {
    return (
      <section className="forwardDryRunIntent" aria-label="격리 dry-run 요청">
        <h3>격리 dry-run</h3>
        <p>격리 dry-run을 요청할 수 없습니다.</p>
      </section>
    )
  }

  return (
    <section className="forwardDryRunIntent" aria-label="격리 dry-run 요청">
      <h3>격리 dry-run</h3>
      <p>
        이 작업은 검토한 계획 다이제스트로 서버에 실행 의도만 등록합니다.
        브라우저는 SQL이나 대상 연결 정보를 보내지 않습니다.
      </p>

      {requestState.status === 'created' ? (
        <p role="status" aria-live="polite">
          {requestState.action.reused ? '기존 요청을 재사용했습니다.' : '요청을 접수했습니다.'}
          {' '}실행 {requestState.action.migration_run_uuid}
        </p>
      ) : null}

      {requestState.status === 'error' ? (
        <div role="alert">
          <p>요청 결과를 확인하지 못했습니다. 같은 요청을 안전하게 다시 확인할 수 있습니다.</p>
          <button type="button" onClick={() => void submit()}>
            같은 요청 다시 시도
          </button>
        </div>
      ) : null}

      {requestState.status === 'idle' || requestState.status === 'requesting' ? (
        <button
          type="button"
          disabled={requestState.status === 'requesting'}
          onClick={() => void submit()}
        >
          {requestState.status === 'requesting' ? '요청 중…' : '격리 dry-run 요청'}
        </button>
      ) : null}
    </section>
  )
}
