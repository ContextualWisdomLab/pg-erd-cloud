import { describe, expect, it } from 'vitest'

import { snapshotDetailFromResponse, toPlainText, type SnapshotDetailResponse } from './types'

describe('toPlainText', () => {
  it('preserves display text and strips control characters', () => {
    expect(toPlainText('<script>alert("x")</script>\u0000')).toBe(
      '<script>alert("x")</script>'
    )
    expect(toPlainText('hello & < > " \'')).toBe('hello & < > " \'')
    expect(toPlainText('hello\x00world')).toBe('hello world')
  })

  it('returns null for non-string or empty values', () => {
    expect(toPlainText(null)).toBeNull()
    expect(toPlainText('')).toBeNull()
    expect(toPlainText(123)).toBeNull()
  })
})

describe('snapshotDetailFromResponse', () => {
  it('maps error_message to PlainText', () => {
    const mockResponse: SnapshotDetailResponse = {
      schema_snapshot_uuid: '123',
      status: 'completed',
      schema_filter: null,
      snapshot_json: null,
      error_message: '<error>'
    }

    const detail = snapshotDetailFromResponse(mockResponse)
    expect(detail.error_message).toBe('<error>')
  })

  it('maps arbitrary error_message values safely', () => {
    const response: SnapshotDetailResponse = {
      schema_snapshot_uuid: 'uuid',
      status: 'ok',
      schema_filter: null,
      error_message: 'bad <error>',
      snapshot_json: null
    }

    const result = snapshotDetailFromResponse(response)
    expect(result.error_message).toBe('bad <error>')
  })
})
