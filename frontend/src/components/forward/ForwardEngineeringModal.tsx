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
  const [passedDryRun, setPassedDryRun] = useState<{
    scope: string
    run: MigrationRun
  } | null>(null)
  const runScope = `${planId}\u0000${runId ?? ''}`

  useEffect(() => {
    if (!isOpen) {
      setCreatedRun(null)
      setReviewedPlan(null)
      setPassedDryRun(null)
    }
  }, [isOpen])

  useEffect(() => {
    setPassedDryRun(null)
  }, [runScope])

  if (!isOpen) return null

  const activeRunId = createdRun?.scope === runScope ? createdRun.runId : runId
  const handleRunLoaded = (loadedRun: MigrationRun | null) => {
    if (
      loadedRun?.run_kind === 'dry_run'
      && loadedRun.state === 'passed'
      && loadedRun.migration_plan_uuid === planId
    ) {
      setPassedDryRun({ scope: runScope, run: loadedRun })
    }
  }

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
            <RunStatusSurface runId={activeRunId} onRunLoaded={handleRunLoaded} />
          ) : null}
          {reviewedPlan
            && passedDryRun?.scope === runScope
            && reviewedPlan.migration_plan_uuid === planId ? (
              <ApplyIntentPanel
                plan={reviewedPlan}
                passedDryRun={passedDryRun.run}
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
