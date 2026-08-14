import { useEffect, useState } from 'react'

import type { MigrationPlan, MigrationRun } from '../../types'
import { useDialogAccessibility } from '../modals/useDialogAccessibility'
import { ApplyIntentPanel } from './ApplyIntentPanel'
import { PlanReviewSurface } from './PlanReviewSurface'
import { RunStatusSurface } from './RunStatusSurface'

type ForwardEngineeringModalProps = {
  isOpen: boolean
  planId: string
  runId?: string
  onClose: () => void
}

export function ForwardEngineeringModal({
  isOpen,
  planId,
  runId,
  onClose,
}: ForwardEngineeringModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onClose)
  const [createdRun, setCreatedRun] = useState<{
    scope: string
    runId: string
  } | null>(null)
  const [reviewedPlan, setReviewedPlan] = useState<MigrationPlan | null>(null)
  const [observedRun, setObservedRun] = useState<MigrationRun | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setCreatedRun(null)
      setReviewedPlan(null)
      setObservedRun(null)
    }
  }, [isOpen])

  if (!isOpen) return null

  const runScope = `${planId}\u0000${runId ?? ''}`
  const activeRunId = createdRun?.scope === runScope ? createdRun.runId : runId

  return (
    <div className="forwardEngineeringModalOverlay">
      <div
        ref={dialogRef}
        className="forwardEngineeringModal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="forward-engineering-title"
        tabIndex={-1}
      >
        <header className="forwardEngineeringModal__header">
          <h1 id="forward-engineering-title">Forward Engineering</h1>
          <button type="button" onClick={onClose} aria-label="Forward Engineering 닫기">
            닫기
          </button>
        </header>
        <div className="forwardEngineeringModal__body">
          <PlanReviewSurface
            planId={planId}
            onPlanLoaded={setReviewedPlan}
            onRunCreated={(newRunId) => setCreatedRun({
              scope: runScope,
              runId: newRunId,
            })}
            renderCreatedRunStatus={false}
          />
          {activeRunId ? (
            <RunStatusSurface runId={activeRunId} onRunLoaded={setObservedRun} />
          ) : null}
          {reviewedPlan
            && observedRun
            && reviewedPlan.migration_plan_uuid === planId
            && observedRun.migration_run_uuid === activeRunId ? (
              <ApplyIntentPanel
                plan={reviewedPlan}
                passedDryRun={observedRun}
                onRunCreated={(newRunId) => setCreatedRun({
                  scope: runScope,
                  runId: newRunId,
                })}
              />
            ) : null}
        </div>
      </div>
    </div>
  )
}
