import { describe, expect, it } from 'vitest'

import { toPlainText, snapshotDetailFromResponse } from './types'

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
  it('converts error_message using toPlainText', () => {
    const input = {
      schema_snapshot_uuid: '123',
      status: 'failed',
      schema_filter: null,
      snapshot_json: null,
      error_message: 'Some <error>'
    };

    // @ts-expect-error test
    const output = snapshotDetailFromResponse(input);
    expect(output.error_message).toBe('Some &lt;error&gt;');
  });
});
