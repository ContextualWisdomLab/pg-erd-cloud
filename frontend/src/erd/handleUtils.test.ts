import { describe, expect, it } from 'vitest'

import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId } from './handleUtils'

function legacySanitizeHandleId(columnName: string): string {
  const encoded = Array.from(columnName, (character) =>
    character.codePointAt(0)!.toString(16).padStart(4, '0'),
  ).join('-')
  return `c-${encoded || 'empty'}`
}

describe('handleUtils', () => {
  describe('sanitizeHandleId', () => {
    it('encodes a simple ASCII string', () => {
      expect(sanitizeHandleId('id')).toBe('c-0069-0064')
    })

    it('preserves the empty-input sentinel', () => {
      expect(sanitizeHandleId('')).toBe('c-empty')
    })

    it('encodes punctuation without normalization', () => {
      expect(sanitizeHandleId('user_id')).toBe('c-0075-0073-0065-0072-005f-0069-0064')
    })

    it('encodes Hangul by Unicode code point', () => {
      expect(sanitizeHandleId('id_가')).toBe('c-0069-0064-005f-ac00')
    })

    it('encodes astral emoji as one Unicode code point', () => {
      expect(sanitizeHandleId('id_🚀')).toBe('c-0069-0064-005f-1f680')
    })

    it.each([
      '',
      'userID_Test',
      'e\u0301',
      '👩‍👩‍👧‍👦',
      '\u{10ffff}',
      '\ud800',
      'schema.table-name',
      '한글과English_123',
    ])('matches the predecessor encoding for %j', (columnName) => {
      expect(sanitizeHandleId(columnName)).toBe(legacySanitizeHandleId(columnName))
    })
  })

  describe('sourceColumnHandleId', () => {
    it('prepends the source prefix', () => {
      expect(sourceColumnHandleId('id')).toBe('src-c-0069-0064')
    })
  })

  describe('targetColumnHandleId', () => {
    it('prepends the target prefix', () => {
      expect(targetColumnHandleId('id')).toBe('tgt-c-0069-0064')
    })
  })
})
