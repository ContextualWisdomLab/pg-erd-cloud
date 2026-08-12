import { useDialogAccessibility } from '../modals/useDialogAccessibility'
import { PlanReviewSurface } from './PlanReviewSurface'

type ForwardEngineeringModalProps = {
  isOpen: boolean
  planId: string
  onClose: () => void
}

export function ForwardEngineeringModal({
  isOpen,
  planId,
  onClose,
}: ForwardEngineeringModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onClose)

  if (!isOpen) return null

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
          <PlanReviewSurface planId={planId} />
        </div>
      </div>
    </div>
  )
}
