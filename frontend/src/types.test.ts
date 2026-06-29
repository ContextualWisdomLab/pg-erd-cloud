import { describe, expect, it } from 'vitest'

import { toPlainText, snapshotDetailFromResponse, SnapshotDetailResponse } from './types'

describe('toPlainText', () => {
  it('escapes html-sensitive characters', () => {
    expect(toPlainText('&')).toBe('&amp;')
    expect(toPlainText('<')).toBe('&lt;')
    expect(toPlainText('>')).toBe('&gt;')
    expect(toPlainText('"')).toBe('&quot;')
    expect(toPlainText("'")).toBe('&#39;')
    expect(toPlainText('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
    )
  })

  it('strips control characters', () => {
    // control characters get replaced by space, then trimmed. so just control chars means empty string -> null
    expect(toPlainText('\u0000\u0008\u000B\u000C\u000E\u001F\u007F')).toBeNull()
    // control characters with text
    expect(toPlainText('a\u0000b')).toBe('a b')
  })

  it('returns null for purely whitespace strings', () => {
    expect(toPlainText('   ')).toBe(null)
    expect(toPlainText('\t\n')).toBe(null)
  })

  it('trims whitespace', () => {
    expect(toPlainText('  hello world  ')).toBe('hello world')
  })

  it('returns null for non-string or empty values', () => {
    expect(toPlainText(null)).toBeNull()
    expect(toPlainText(undefined)).toBeNull()
    expect(toPlainText('')).toBeNull()
    expect(toPlainText(123)).toBeNull()
    expect(toPlainText(true)).toBeNull()
    expect(toPlainText({})).toBeNull()
    expect(toPlainText([])).toBeNull()
  })
})

describe('snapshotDetailFromResponse', () => {
  it('sanitizes error_message correctly', () => {
    const response: SnapshotDetailResponse = {
      schema_snapshot_uuid: 'uuid-123',
      status: 'failed',
      schema_filter: null,
      snapshot_json: null,
      error_message: '<script>alert("error")</script>'
    }

    const detail = snapshotDetailFromResponse(response)

    expect(detail.error_message).toBe('&lt;script&gt;alert(&quot;error&quot;)&lt;/script&gt;')
    expect(detail.schema_snapshot_uuid).toBe('uuid-123')
    expect(detail.status).toBe('failed')
  })

  it('handles null error_message', () => {
    const response: SnapshotDetailResponse = {
      schema_snapshot_uuid: 'uuid-123',
      status: 'failed',
      schema_filter: null,
      snapshot_json: null,
      error_message: null
    }

    const detail = snapshotDetailFromResponse(response)

    expect(detail.error_message).toBeNull()
  })

  it('handles non-string error_message', () => {
    const response: SnapshotDetailResponse = {
      schema_snapshot_uuid: 'uuid-123',
      status: 'failed',
      schema_filter: null,
      snapshot_json: null,
      error_message: 123
    }

    const detail = snapshotDetailFromResponse(response)

    expect(detail.error_message).toBeNull()
  })
})
