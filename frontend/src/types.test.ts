import { describe, expect, it } from 'vitest'

import { toPlainText, snapshotDetailFromResponse, type SnapshotDetailResponse } from './types'

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
  it('maps error_message to PlainText', () => {
    const mockResponse: SnapshotDetailResponse = {
      schema_snapshot_uuid: '123',
      status: 'completed',
      schema_filter: null,
      snapshot_json: null,
      error_message: '<error>'
    }

    const detail = snapshotDetailFromResponse(mockResponse)
    expect(detail.error_message).toBe('&lt;error&gt;')
  })
})
