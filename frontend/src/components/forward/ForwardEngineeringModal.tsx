import { useEffect, useState } from 'react'

import { useDialogAccessibility } from '../modals/useDialogAccessibility'
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

  useEffect(() => {
    if (!isOpen) setCreatedRun(null)
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
            onRunCreated={(newRunId) => setCreatedRun({
              scope: runScope,
              runId: newRunId,
            })}
            renderCreatedRunStatus={false}
          />
          {activeRunId ? <RunStatusSurface runId={activeRunId} /> : null}
        </div>
      </div>
    </div>
  )
}
