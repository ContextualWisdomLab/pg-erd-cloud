import { useEffect, useState } from 'react'

import { getMigrationRun } from '../../api'
import type { MigrationRun } from '../../types'
import { RunStatusPanel } from './RunStatusPanel'

type RunStatusSurfaceProps = {
  runId: string
}

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; run: MigrationRun }
  | { status: 'error' }

export function RunStatusSurface({ runId }: RunStatusSurfaceProps) {
  const [attempt, setAttempt] = useState(0)
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    let active = true
    setLoadState({ status: 'loading' })

    void getMigrationRun(runId).then(
      (run) => {
        if (active) setLoadState({ status: 'ready', run })
      },
      () => {
        if (active) setLoadState({ status: 'error' })
      },
    )

    return () => {
      active = false
    }
  }, [attempt, runId])

  if (loadState.status === 'loading') {
    return <p role="status" aria-live="polite">실행 상태를 불러오는 중입니다.</p>
  }

  if (loadState.status === 'error') {
    return (
      <div role="alert">
        <p>실행 상태를 불러오지 못했습니다.</p>
        <button type="button" onClick={() => setAttempt((value) => value + 1)}>
          다시 시도
        </button>
      </div>
    )
  }

  return <RunStatusPanel run={loadState.run} />
}
