import { describe, expect, it } from 'vitest'

import {
  decodeHandleId,
  decodeSourceColumnHandleId,
  decodeTargetColumnHandleId,
  sanitizeHandleId,
  sourceColumnHandleId,
  targetColumnHandleId,
} from './handleUtils'

describe('handleUtils', () => {
  describe('sanitizeHandleId', () => {
    it('encodes a simple ASCII string', () => {
      expect(sanitizeHandleId('id')).toBe('c-0069-0064')
    })

    it('handles the empty string', () => {
      expect(sanitizeHandleId('')).toBe('c-empty')
    })

    it('handles special characters', () => {
      expect(sanitizeHandleId('user_id')).toBe(
        'c-0075-0073-0065-0072-005f-0069-0064',
      )
    })

    it('handles Unicode characters', () => {
      expect(sanitizeHandleId('id_가')).toBe('c-0069-0064-005f-ac00')
    })

    it('handles supplementary code points', () => {
      expect(sanitizeHandleId('id_🚀')).toBe('c-0069-0064-005f-1f680')
    })
  })

  describe('sourceColumnHandleId', () => {
    it('prepends src- to a sanitized identifier', () => {
      expect(sourceColumnHandleId('id')).toBe('src-c-0069-0064')
    })
  })

  describe('targetColumnHandleId', () => {
    it('prepends tgt- to a sanitized identifier', () => {
      expect(targetColumnHandleId('id')).toBe('tgt-c-0069-0064')
    })
  })

  describe('decodeHandleId', () => {
    it('decodes every supported canonical prefix', () => {
      expect(decodeHandleId('c-0069-0064')).toBe('id')
      expect(decodeHandleId('src-c-0069-0064')).toBe('id')
      expect(decodeHandleId('tgt-c-0069-0064')).toBe('id')
    })

    it('handles the canonical empty identifier for every supported prefix', () => {
      expect(decodeHandleId('c-empty')).toBe('')
      expect(decodeHandleId('src-c-empty')).toBe('')
      expect(decodeHandleId('tgt-c-empty')).toBe('')
    })

    it('decodes special characters', () => {
      expect(
        decodeHandleId('c-0075-0073-0065-0072-005f-0069-0064'),
      ).toBe('user_id')
    })

    it('decodes Unicode and supplementary code points', () => {
      expect(decodeHandleId('c-0069-0064-005f-ac00')).toBe('id_가')
      expect(decodeHandleId('c-0069-0064-005f-1f680')).toBe('id_🚀')
    })

    it.each([
      null,
      undefined,
      '',
      'invalid-format',
      'src-c',
      'c',
    ])('returns null for absent or structurally incomplete input %s', (value) => {
      expect(decodeHandleId(value)).toBeNull()
    })

    it.each([
      'c-0069-006A',
      'c-0069junk-0064',
      'foo-c-0069',
      'src-foo-0069',
      'c-empty-0069',
      'c-200000',
      'c-0069--0064',
      'c-069',
      'c-000069',
      'c-01f680',
      'src-c-000069',
      'tgt-c-01f680',
    ])('rejects malformed or non-canonical input %s', (value) => {
      expect(decodeHandleId(value)).toBeNull()
    })

    it.each(['', 'id', 'id_가', 'id_🚀', 'column-with punctuation!'])(
      'round-trips a sanitized column name %s',
      (columnName) => {
        expect(decodeHandleId(sanitizeHandleId(columnName))).toBe(columnName)
        expect(decodeHandleId(sourceColumnHandleId(columnName))).toBe(columnName)
        expect(decodeHandleId(targetColumnHandleId(columnName))).toBe(columnName)
      },
    )
  })

  describe('role-specific decoders', () => {
    it('accepts only a source handle in the source decoder', () => {
      expect(decodeSourceColumnHandleId('src-c-0069-0064')).toBe('id')
      expect(decodeSourceColumnHandleId('src-c-empty')).toBe('')
      expect(decodeSourceColumnHandleId('tgt-c-0069-0064')).toBeNull()
      expect(decodeSourceColumnHandleId('c-0069-0064')).toBeNull()
    })

    it('accepts only a target handle in the target decoder', () => {
      expect(decodeTargetColumnHandleId('tgt-c-0069-0064')).toBe('id')
      expect(decodeTargetColumnHandleId('tgt-c-empty')).toBe('')
      expect(decodeTargetColumnHandleId('src-c-0069-0064')).toBeNull()
      expect(decodeTargetColumnHandleId('c-0069-0064')).toBeNull()
    })
  })
})
