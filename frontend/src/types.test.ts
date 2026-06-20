import { describe, expect, it } from 'vitest'

import { toPlainText } from './types'

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
