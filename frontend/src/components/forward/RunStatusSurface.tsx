import { useEffect, useRef, useState } from 'react'

import { getMigrationRun } from '../../api'
import type { MigrationRun } from '../../types'
import { RunCancellationControl } from './RunCancellationControl'
import { RunStatusPanel } from './RunStatusPanel'
import { TERMINAL_RUN_STATES } from './runStates'

type RunStatusSurfaceProps = {
  runId: string
  onRunLoaded?: (run: MigrationRun | null) => void
  refreshIntervalMs?: number
}

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; run: MigrationRun }
  | { status: 'error' }

export function RunStatusSurface({
  runId,
  onRunLoaded,
  refreshIntervalMs = 2_000,
}: RunStatusSurfaceProps) {
  const [attempt, setAttempt] = useState(0)
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const onRunLoadedRef = useRef(onRunLoaded)

  useEffect(() => {
    onRunLoadedRef.current = onRunLoaded
  }, [onRunLoaded])

  useEffect(() => {
    let active = true
    let refreshTimer: ReturnType<typeof setTimeout> | undefined
    setLoadState({ status: 'loading' })
    onRunLoadedRef.current?.(null)

    const load = async () => {
      try {
        const run = await getMigrationRun(runId)
        if (!active) return
        setLoadState({ status: 'ready', run })
        onRunLoadedRef.current?.(run)
        if (!TERMINAL_RUN_STATES.has(run.state)) {
          refreshTimer = setTimeout(() => void load(), Math.max(1, refreshIntervalMs))
        }
      } catch {
        if (active) setLoadState({ status: 'error' })
      }
    }

    void load()

    return () => {
      active = false
      if (refreshTimer !== undefined) clearTimeout(refreshTimer)
    }
  }, [attempt, refreshIntervalMs, runId])

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

  return (
    <>
      <RunStatusPanel run={loadState.run} />
      <RunCancellationControl
        run={loadState.run}
        onRefresh={() => setAttempt((value) => value + 1)}
      />
    </>
  )
}
