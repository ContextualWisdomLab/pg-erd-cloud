import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { MigrationRun } from '../../types'
import { RunStatusPanel } from './RunStatusPanel'
import { isTerminalMigrationRunState } from './runStates'

const run: MigrationRun = {
  migration_run_uuid: 'run-1',
  project_space_uuid: 'project-1',
  migration_plan_uuid: 'plan-1',
  run_kind: 'dry_run',
  state: 'passed',
  state_version: 3,
  plan_digest: 'a'.repeat(64),
  requested_by_user_uuid: 'user-1',
  cancellation_requested: false,
  observed_base_digest: 'b'.repeat(64),
  evidence: { request_id: 'must-not-render', secret: 'must-not-render' },
  error_code: null,
  created_at: '2026-08-12T05:00:00Z',
  updated_at: '2026-08-12T05:02:00Z',
  started_at: '2026-08-12T05:01:00Z',
  finished_at: '2026-08-12T05:02:00Z',
  events: [
    {
      sequence_number: 1,
      event_type: 'run_queued<img src=x onerror=alert(1)>',
      state_before: null,
      state_after: 'queued',
      evidence: { request_id: 'event-must-not-render' },
      previous_event_digest: null,
      event_digest: 'c'.repeat(64),
      actor_user_uuid: 'user-1',
      created_at: '2026-08-12T05:00:00Z',
    },
    {
      sequence_number: 2,
      event_type: 'isolated_dry_run_succeeded',
      state_before: 'sandbox_running',
      state_after: 'live_preflight_running',
      evidence: { statement_count: 1 },
      previous_event_digest: 'c'.repeat(64),
      event_digest: 'd'.repeat(64),
      actor_user_uuid: null,
      created_at: '2026-08-12T05:01:30Z',
    },
  ],
}

afterEach(cleanup)

describe('RunStatusPanel', () => {
  it('announces the exact state and its bounded terminal meaning', () => {
    render(<RunStatusPanel run={run} />)

    expect(screen.getByRole('status', { name: '마이그레이션 실행 상태' })).toHaveTextContent(
      '격리 검증 및 읽기 전용 사전 점검 통과',
    )
    expect(screen.getByText('라이브 대상에서 DDL을 실행했다는 의미가 아닙니다.')).toBeInTheDocument()
    expect(screen.getByText('run-1')).toBeInTheDocument()
    expect(screen.getByText('b'.repeat(64))).toBeInTheDocument()
  })

  it('renders the append-only digest chain as text without exposing evidence payloads', () => {
    const { container } = render(<RunStatusPanel run={run} />)

    expect(
      screen.getByRole('heading', { name: '#1 run_queued<img src=x onerror=alert(1)>' }),
    ).toBeInTheDocument()
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(screen.getAllByText('c'.repeat(64))).toHaveLength(2)
    expect(screen.getByText('d'.repeat(64))).toBeInTheDocument()
    expect(screen.queryByText(/must-not-render/)).not.toBeInTheDocument()
    expect(screen.getByText('서버가 검증한 이벤트 메타데이터만 표시합니다.')).toBeInTheDocument()
  })

  it('surfaces cancellation intent and a sanitized error code without inventing success', () => {
    render(
      <RunStatusPanel
        run={{
          ...run,
          state: 'outcome_unknown',
          cancellation_requested: true,
          error_code: 'commit_outcome_unknown',
        }}
      />,
    )

    expect(screen.getByRole('alert', { name: '취소 요청' })).toBeInTheDocument()
    expect(screen.getByRole('alert', { name: '실행 오류' })).toHaveTextContent(
      'commit_outcome_unknown',
    )
    expect(screen.getByText('결과가 불명확하며 자동 재실행이 금지됩니다.')).toBeInTheDocument()
  })

  it('announces acknowledged cancellation as terminal without implying live DDL', () => {
    render(
      <RunStatusPanel
        run={{
          ...run,
          state: 'cancelled',
          cancellation_requested: true,
          error_code: null,
        }}
      />,
    )

    expect(isTerminalMigrationRunState('cancelled')).toBe(true)
    expect(screen.getByRole('status', { name: '마이그레이션 실행 상태' })).toHaveTextContent(
      '취소 완료',
    )
    expect(screen.getByText('취소가 확인됐으며 라이브 DDL을 실행하지 않았습니다.')).toBeInTheDocument()
    expect(screen.getByRole('alert', { name: '취소 완료' })).toBeInTheDocument()
    expect(screen.queryByRole('alert', { name: '취소 요청' })).not.toBeInTheDocument()
  })
})
