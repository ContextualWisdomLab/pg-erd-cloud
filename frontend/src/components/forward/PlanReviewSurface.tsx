import { useEffect, useRef, useState } from 'react'

import { getMigrationPlan } from '../../api'
import type { MigrationPlan } from '../../types'
import { DryRunIntentPanel } from './DryRunIntentPanel'
import { PlanReviewPanel } from './PlanReviewPanel'
import { RunStatusSurface } from './RunStatusSurface'

type PlanReviewSurfaceProps = {
  planId: string
  onPlanLoaded?: (plan: MigrationPlan | null) => void
  onRunCreated?: (runId: string) => void
  renderCreatedRunStatus?: boolean
}

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; plan: MigrationPlan }
  | { status: 'error' }

export function PlanReviewSurface({
  planId,
  onPlanLoaded,
  onRunCreated,
  renderCreatedRunStatus = true,
}: PlanReviewSurfaceProps) {
  const [attempt, setAttempt] = useState(0)
  const [createdRunId, setCreatedRunId] = useState<string | null>(null)
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const onPlanLoadedRef = useRef(onPlanLoaded)

  useEffect(() => {
    onPlanLoadedRef.current = onPlanLoaded
  }, [onPlanLoaded])

  useEffect(() => {
    let active = true
    setCreatedRunId(null)
    setLoadState({ status: 'loading' })
    onPlanLoadedRef.current?.(null)

    void getMigrationPlan(planId).then(
      (plan) => {
        if (active) {
          setLoadState({ status: 'ready', plan })
          onPlanLoadedRef.current?.(plan)
        }
      },
      () => {
        if (active) setLoadState({ status: 'error' })
      },
    )

    return () => {
      active = false
    }
  }, [attempt, planId])

  if (loadState.status === 'loading') {
    return <p role="status" aria-live="polite">계획을 불러오는 중입니다.</p>
  }

  if (loadState.status === 'error') {
    return (
      <div role="alert">
        <p>계획을 불러오지 못했습니다.</p>
        <button type="button" onClick={() => setAttempt((value) => value + 1)}>
          다시 시도
        </button>
      </div>
    )
  }

  const handleRunCreated = (runId: string) => {
    setCreatedRunId(runId)
    onRunCreated?.(runId)
  }

  return (
    <>
      <PlanReviewPanel plan={loadState.plan} />
      <DryRunIntentPanel plan={loadState.plan} onRunCreated={handleRunCreated} />
      {renderCreatedRunStatus && createdRunId
        ? <RunStatusSurface runId={createdRunId} />
        : null}
    </>
  )
}
