import { describe, it, expect } from 'vitest';
import { sanitizeTableName } from './securityUtils';

describe('sanitizeTableName', () => {
  it('should return the same string if it contains only alphanumeric characters and underscores', () => {
    expect(sanitizeTableName('valid_table_name_1')).toBe('valid_table_name_1');
  });

  it('should remove spaces', () => {
    expect(sanitizeTableName('table name')).toBe('tablename');
  });

  it('should remove special characters', () => {
    expect(sanitizeTableName('table-name!')).toBe('tablename');
    expect(sanitizeTableName('table@name#$')).toBe('tablename');
  });

  it('should handle empty strings', () => {
    expect(sanitizeTableName('')).toBe('');
  });

  it('should sanitize strings resembling SQL injection', () => {
    expect(sanitizeTableName('users; DROP TABLE users;')).toBe('usersDROPTABLEusers');
    expect(sanitizeTableName('users" OR "1"="1')).toBe('usersOR11');
  });
});
