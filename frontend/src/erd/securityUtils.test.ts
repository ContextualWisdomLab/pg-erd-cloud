import { describe, expect, it } from 'vitest';

import { sanitizeTableName } from './securityUtils';

describe('sanitizeTableName', () => {
  it('preserves ASCII alphanumeric characters and underscores', () => {
    expect(sanitizeTableName('valid_Table_Name123')).toBe('valid_Table_Name123');
    expect(sanitizeTableName('Users')).toBe('Users');
    expect(sanitizeTableName('table_1')).toBe('table_1');
  });

  it('removes whitespace and punctuation', () => {
    expect(sanitizeTableName('invalid table name')).toBe('invalidtablename');
    expect(sanitizeTableName('  padded  ')).toBe('padded');
    expect(sanitizeTableName('table-name')).toBe('tablename');
    expect(sanitizeTableName('user@domain')).toBe('userdomain');
    expect(sanitizeTableName('table!@#$%^&*()_+={}|[]\\:";\'<>?,./')).toBe('table_');
  });

  it('reduces SQL-shaped text to the identifier allowlist', () => {
    expect(sanitizeTableName('drop table;--')).toBe('droptable');
    expect(sanitizeTableName('SELECT * FROM users')).toBe('SELECTFROMusers');
    expect(sanitizeTableName('users; DROP TABLE audit_log;--')).toBe(
      'usersDROPTABLEaudit_log',
    );
  });

  it('removes non-ASCII Unicode and emoji characters', () => {
    expect(sanitizeTableName('table_이름🚀')).toBe('table_');
  });

  it('handles empty and entirely invalid input', () => {
    expect(sanitizeTableName('')).toBe('');
    expect(sanitizeTableName('!!! @@@')).toBe('');
  });
});
