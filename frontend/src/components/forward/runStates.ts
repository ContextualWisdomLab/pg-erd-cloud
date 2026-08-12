import type { MigrationRunState } from '../../types'

export const TERMINAL_RUN_STATES: ReadonlySet<MigrationRunState> = new Set([
  'passed',
  'drifted',
  'failed',
  'verified',
  'drifted_no_apply',
  'not_applied',
  'verification_failed',
  'failed_rolled_back',
  'applied_with_drift',
  'outcome_unknown',
])

export function isTerminalMigrationRunState(state: MigrationRunState): boolean {
  return TERMINAL_RUN_STATES.has(state)
}
