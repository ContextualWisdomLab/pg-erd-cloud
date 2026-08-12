import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { MigrationPlan } from '../../types'
import { PlanReviewPanel } from './index'

const statement: MigrationPlan['statements'][number] = {
  kind: 'add_column',
  target: '판매.주문.배송지',
  object_ref: {
    database: null,
    schema_name: '판매',
    table_name: '주문',
    column_name: '배송지',
  },
  sql: 'ALTER TABLE "판매"."주문" ADD COLUMN "배송지" text;',
  transactional: true,
  dependencies: ['table:판매.주문'],
  dependency_refs: [{
    database: null,
    schema_name: '판매',
    table_name: '주문',
    column_name: null,
  }],
  reversible: true,
  risk: {
    severity: 'warning',
    lock_mode: 'ACCESS EXCLUSIVE',
    possible_rewrite: false,
    table_scan: false,
    data_loss: false,
    detail: '기존 행은 변경하지 않지만 테이블 잠금이 필요합니다.',
  },
  required_privileges: ['ALTER'],
  preconditions: [{
    kind: 'table_is_empty',
    object_ref: {
      schema_name: '판매',
      table_name: '주문',
    },
  }],
}

const plan: MigrationPlan = {
  migration_plan_uuid: '11111111-1111-4111-8111-111111111111',
  project_space_uuid: '22222222-2222-4222-8222-222222222222',
  schema_model_revision_uuid: '33333333-3333-4333-8333-333333333333',
  db_connection_uuid: '44444444-4444-4444-8444-444444444444',
  base_schema_snapshot_uuid: '55555555-5555-4555-8555-555555555555',
  plan_digest: 'a'.repeat(64),
  base_digest: 'b'.repeat(64),
  target_digest: 'c'.repeat(64),
  compiler_version: 'pg-plan-v1',
  snapshot_contract_version: 1,
  postgresql_major: 16,
  created_by_user_uuid: '66666666-6666-4666-8666-666666666666',
  created_at: '2026-08-12T05:00:00Z',
  can_dry_run: true,
  requires_destructive_confirmation: false,
  statements: [statement],
  proposed_statements: [],
  blockers: [],
  risk_summary: { safe: 0, warning: 1, destructive: 0 },
  expires_at: '2026-08-13T05:00:00Z',
}

afterEach(cleanup)

describe('PlanReviewPanel', () => {
  it('presents immutable provenance, risk, and structured executable statements', () => {
    render(<PlanReviewPanel plan={plan} />)

    expect(screen.getByRole('heading', { name: '마이그레이션 계획 검토' })).toBeInTheDocument()
    const provenance = screen.getByRole('region', { name: '계획 출처' })
    expect(provenance).toHaveTextContent(plan.migration_plan_uuid)
    expect(provenance).toHaveTextContent(plan.schema_model_revision_uuid)
    expect(provenance).toHaveTextContent(plan.base_schema_snapshot_uuid)
    expect(provenance).toHaveTextContent('PostgreSQL 16')
    expect(provenance).toHaveTextContent(plan.plan_digest)

    const risk = screen.getByRole('region', { name: '위험 요약' })
    expect(within(risk).getByText('경고 1')).toBeInTheDocument()
    expect(within(risk).getByText('파괴적 0')).toBeInTheDocument()

    const executable = screen.getByRole('region', { name: '실행 가능한 문 1개' })
    expect(executable).toHaveTextContent('add_column')
    expect(executable).toHaveTextContent('판매.주문.배송지')
    expect(executable).toHaveTextContent('ACCESS EXCLUSIVE')
    expect(executable).toHaveTextContent('ALTER')
    expect(executable).toHaveTextContent('table:판매.주문')
    expect(executable).toHaveTextContent('판매.주문')
    expect(executable).toHaveTextContent('table_is_empty')
    expect(executable).toHaveTextContent(statement.sql)
  })

  it('keeps blocked SQL review-only and exposes blockers as an alert', () => {
    const hostileSql = 'ALTER TABLE x ADD COLUMN y text; <img src=x onerror=alert(1)>'
    render(
      <PlanReviewPanel
        plan={{
          ...plan,
          can_dry_run: false,
          statements: [],
          proposed_statements: [{
            ...statement,
            sql: hostileSql,
            transactional: false,
            reversible: false,
          }],
          blockers: [{
            code: 'generated_column_unsupported',
            object: '판매.주문.합계',
            object_ref: {
              database: null,
              schema_name: '판매',
              table_name: '주문',
              column_name: '합계',
            },
            detail: '생성 열은 v1에서 지원하지 않습니다.',
          }],
        }}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('generated_column_unsupported')
    expect(screen.getByRole('region', { name: '실행 가능한 문 0개' })).toBeEmptyDOMElement()
    const proposals = screen.getByRole('region', { name: '검토 전용 제안 1개' })
    expect(proposals).toHaveTextContent(hostileSql)
    expect(proposals).toHaveTextContent('아니요')
    expect(proposals).toHaveTextContent('불가')
    expect(proposals.querySelector('img')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
