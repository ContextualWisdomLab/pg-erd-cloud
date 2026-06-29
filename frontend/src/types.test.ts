import { describe, expect, it } from 'vitest'

import { toPlainText, snapshotDetailFromResponse, SnapshotDetailResponse } from './types'

describe('toPlainText', () => {
  it('escapes html-sensitive characters and strips control characters', () => {
    expect(toPlainText('<script>alert("x")</script>\u0000')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
    )
  })

  it('returns null for non-string or empty values', () => {
    expect(toPlainText(null)).toBeNull()
    expect(toPlainText('')).toBeNull()
  })
})

describe('snapshotDetailFromResponse', () => {
  it('converts error_message to plain text and passes through other fields', () => {
    const response: SnapshotDetailResponse = {
      schema_snapshot_uuid: 'uuid-123',
      status: 'failed',
      schema_filter: null,
      snapshot_json: null,
      error_message: '<error>bad error!</error>'
    }

    const detail = snapshotDetailFromResponse(response)

    expect(detail).toEqual({
      schema_snapshot_uuid: 'uuid-123',
      status: 'failed',
      schema_filter: null,
      snapshot_json: null,
      error_message: '&lt;error&gt;bad error!&lt;/error&gt;'
    })
  })

  it('handles null or invalid error_message correctly', () => {
    const response: SnapshotDetailResponse = {
      schema_snapshot_uuid: 'uuid-456',
      status: 'success',
      schema_filter: 'public',
      snapshot_json: {},
      error_message: null
    }

    const detail = snapshotDetailFromResponse(response)

    expect(detail).toEqual({
      schema_snapshot_uuid: 'uuid-456',
      status: 'success',
      schema_filter: 'public',
      snapshot_json: {},
      error_message: null
    })
  })
})
