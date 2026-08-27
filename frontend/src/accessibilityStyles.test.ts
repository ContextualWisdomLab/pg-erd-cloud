import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const unavailableActionStyles = readFileSync(
  new URL('./accessibility.css', import.meta.url),
  'utf8',
);

describe('aria-disabled visual contract', () => {
  it('keeps unavailable buttons visually distinct without removing focusability', () => {
    expect(unavailableActionStyles).toContain('button[aria-disabled="true"]');
    expect(unavailableActionStyles).toContain('opacity: 0.6');
    expect(unavailableActionStyles).toContain('cursor: not-allowed');
    expect(unavailableActionStyles).toContain(
      'background-color: var(--color-surface-muted)',
    );
    expect(unavailableActionStyles).toContain('color: var(--color-disabled)');
    expect(unavailableActionStyles).not.toContain('pointer-events: none');
  });
});
