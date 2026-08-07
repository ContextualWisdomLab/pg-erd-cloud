import { describe, it, expect } from 'vitest';
import { sanitizeTableName } from './securityUtils';

describe('sanitizeTableName', () => {
  it('allows alphanumeric characters and underscores', () => {
    expect(sanitizeTableName('valid_table_name_123')).toBe('valid_table_name_123');
    expect(sanitizeTableName('Users')).toBe('Users');
    expect(sanitizeTableName('table_1')).toBe('table_1');
  });

  it('removes spaces', () => {
    expect(sanitizeTableName('table name')).toBe('tablename');
    expect(sanitizeTableName('  padded  ')).toBe('padded');
  });

  it('removes special characters', () => {
    expect(sanitizeTableName('table-name')).toBe('tablename');
    expect(sanitizeTableName('user@domain')).toBe('userdomain');
    expect(sanitizeTableName('drop table;--')).toBe('droptable');
    expect(sanitizeTableName('SELECT * FROM users')).toBe('SELECTFROMusers');
    expect(sanitizeTableName('table!@#$%^&*()_+={}|[]\\:";\'<>?,./')).toBe('table_');
  });

  it('handles empty strings', () => {
    expect(sanitizeTableName('')).toBe('');
  });

  it('returns empty string if input contains only invalid characters', () => {
    expect(sanitizeTableName('!@#$%^&*()')).toBe('');
  });
});
