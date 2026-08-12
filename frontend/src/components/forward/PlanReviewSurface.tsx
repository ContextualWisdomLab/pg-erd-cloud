import { useEffect, useState } from 'react'

import { getMigrationPlan } from '../../api'
import type { MigrationPlan } from '../../types'
import { PlanReviewPanel } from './PlanReviewPanel'

type PlanReviewSurfaceProps = {
  planId: string
}

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; plan: MigrationPlan }
  | { status: 'error' }

export function PlanReviewSurface({ planId }: PlanReviewSurfaceProps) {
  const [attempt, setAttempt] = useState(0)
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    let active = true
    setLoadState({ status: 'loading' })

    void getMigrationPlan(planId).then(
      (plan) => {
        if (active) setLoadState({ status: 'ready', plan })
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

  return <PlanReviewPanel plan={loadState.plan} />
}
