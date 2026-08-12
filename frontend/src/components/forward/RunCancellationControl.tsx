import { useEffect, useRef, useState } from 'react'

import { cancelMigrationRun } from '../../api'
import type { MigrationRun } from '../../types'
import { isTerminalMigrationRunState } from './runStates'

type RunCancellationControlProps = {
  run: MigrationRun
  onRefresh: () => void
}

type CancellationState = 'idle' | 'requesting' | 'outcome_unknown'

export function RunCancellationControl({ run, onRefresh }: RunCancellationControlProps) {
  const [cancellationState, setCancellationState] = useState<CancellationState>('idle')
  const inFlightRef = useRef(false)
  const generationRef = useRef(0)

  useEffect(() => {
    generationRef.current += 1
    inFlightRef.current = false
    setCancellationState('idle')

    return () => {
      generationRef.current += 1
      inFlightRef.current = false
    }
  }, [run.migration_run_uuid])

  const requestCancellation = async () => {
    if (inFlightRef.current) return
    inFlightRef.current = true
    const generation = generationRef.current
    setCancellationState('requesting')

    try {
      await cancelMigrationRun(run.migration_run_uuid, run.state_version)
      if (generation === generationRef.current) onRefresh()
    } catch {
      if (generation === generationRef.current) setCancellationState('outcome_unknown')
    } finally {
      if (generation === generationRef.current) inFlightRef.current = false
    }
  }

  if (run.cancellation_requested || isTerminalMigrationRunState(run.state)) return null

  if (cancellationState === 'outcome_unknown') {
    return (
      <section className="forwardRunAction" aria-label="실행 취소 요청">
        <div role="alert">
          <p>
            취소 요청 결과를 확인하지 못했습니다. 요청을 자동으로 반복하지 말고
            저장된 실행 상태를 다시 확인하세요.
          </p>
          <button type="button" onClick={onRefresh}>실행 상태 새로고침</button>
        </div>
      </section>
    )
  }

  return (
    <section className="forwardRunAction" aria-label="실행 취소 요청">
      <p>
        현재 상태 버전에 취소 의도를 기록합니다. 요청 접수는 즉시 완료 상태를 뜻하지 않습니다.
      </p>
      <button
        type="button"
        disabled={cancellationState === 'requesting'}
        onClick={() => void requestCancellation()}
      >
        {cancellationState === 'requesting' ? '취소 요청 중…' : '실행 취소 요청'}
      </button>
    </section>
  )
}
