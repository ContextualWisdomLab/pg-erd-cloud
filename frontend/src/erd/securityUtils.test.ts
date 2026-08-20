import { describe, it, expect } from 'vitest';
import { sanitizeTableName } from './securityUtils';

describe('securityUtils', () => {
  describe('sanitizeTableName', () => {
    it('should allow alphanumeric characters and underscores', () => {
      expect(sanitizeTableName('valid_Table_Name123')).toBe('valid_Table_Name123');
    });

    it('should remove whitespace', () => {
      expect(sanitizeTableName('invalid table name')).toBe('invalidtablename');
    });

    it('should remove special characters', () => {
      expect(sanitizeTableName('table@#name!')).toBe('tablename');
    });

    it('should remove unicode/emoji characters', () => {
      expect(sanitizeTableName('table_이름🚀')).toBe('table_');
    });

    it('should handle empty string', () => {
      expect(sanitizeTableName('')).toBe('');
    });

    it('should return empty string if all characters are invalid', () => {
      expect(sanitizeTableName('!!! @@@')).toBe('');
    });
  });
});
