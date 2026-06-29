import { describe, it, expect } from 'vitest';
import { toPlainText, snapshotDetailFromResponse, assertNever } from './types';

describe('types', () => {
  it('toPlainText escapes HTML and control chars', () => {
    expect(toPlainText('hello & < > " \'')).toBe('hello &amp; &lt; &gt; &quot; &#39;');
    expect(toPlainText('hello\x00world')).toBe('hello world');
    expect(toPlainText('')).toBeNull();
    expect(toPlainText(123)).toBeNull();
  });

  it('snapshotDetailFromResponse maps correctly', () => {
    const response = {
      schema_snapshot_uuid: 'uuid',
      status: 'ok',
      schema_filter: null,
      error_message: 'bad <error>',
      snapshot_json: null
    };
    const result = snapshotDetailFromResponse(response);
    expect(result.error_message).toBe('bad &lt;error&gt;');
  });

  it('assertNever throws error', () => {
     expect(() => assertNever({} as never)).toThrow();
  });
});
