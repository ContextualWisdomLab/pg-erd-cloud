import { describe, expect, it } from 'vitest'

import {
  decodeHandleId,
  sanitizeHandleId,
  sourceColumnHandleId,
  targetColumnHandleId,
} from './handleUtils'

describe('handleUtils', () => {
  describe('sanitizeHandleId', () => {
    it('should encode a simple ascii string', () => {
      expect(sanitizeHandleId('id')).toBe('c-0069-0064')
    })

    it('should handle empty string', () => {
      expect(sanitizeHandleId('')).toBe('c-empty')
    })

    it('should handle special characters', () => {
      expect(sanitizeHandleId('user_id')).toBe('c-0075-0073-0065-0072-005f-0069-0064')
    })

    it('should handle unicode characters', () => {
      expect(sanitizeHandleId('id_가')).toBe('c-0069-0064-005f-ac00')
    })

    it('should handle emojis', () => {
      expect(sanitizeHandleId('id_🚀')).toBe('c-0069-0064-005f-1f680')
    })
  })

  describe('sourceColumnHandleId', () => {
    it('should prepend src- to sanitized id', () => {
      expect(sourceColumnHandleId('id')).toBe('src-c-0069-0064')
    })
  })

  describe('targetColumnHandleId', () => {
    it('should prepend tgt- to sanitized id', () => {
      expect(targetColumnHandleId('id')).toBe('tgt-c-0069-0064')
    })
  })

  describe('decodeHandleId', () => {
    it.each(['id', 'user_id', 'id_가', 'id_🚀', '', '\ud800'])(
      'round-trips canonical handles for %j',
      (columnName) => {
        expect(decodeHandleId(sanitizeHandleId(columnName))).toBe(columnName)
        expect(decodeHandleId(sourceColumnHandleId(columnName))).toBe(columnName)
        expect(decodeHandleId(targetColumnHandleId(columnName))).toBe(columnName)
      },
    )

    it('should decode canonical prefixes', () => {
      expect(decodeHandleId('c-0069-0064')).toBe('id')
      expect(decodeHandleId('src-c-0069-0064')).toBe('id')
      expect(decodeHandleId('tgt-c-0069-0064')).toBe('id')
    })

    it('should handle empty string payloads', () => {
      expect(decodeHandleId('c-empty')).toBe('')
      expect(decodeHandleId('src-c-empty')).toBe('')
      expect(decodeHandleId('tgt-c-empty')).toBe('')
    })

    it('should handle null, undefined, and missing payloads gracefully', () => {
      expect(decodeHandleId(null)).toBeNull()
      expect(decodeHandleId(undefined)).toBeNull()
      expect(decodeHandleId('')).toBeNull()
      expect(decodeHandleId('src-c')).toBeNull()
      expect(decodeHandleId('tgt-c')).toBeNull()
      expect(decodeHandleId('c')).toBeNull()
    })

    it.each([
      'invalid-format',
      'foo-c-0069',
      'src-foo-c-0069',
      'c-0069junk-0064',
      'c-0069-006A',
      'c-069',
      'c-00069',
      'c-000069',
      'c-0000069',
      'c-empty-0069',
      'c-0069-empty',
      'c-0069--0064',
      'c--0069',
      'c-110000',
      'c-200000',
    ])('rejects non-canonical handle %s', (handleId) => {
      expect(decodeHandleId(handleId)).toBeNull()
    })
  })
})
