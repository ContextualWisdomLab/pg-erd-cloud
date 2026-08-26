import { describe, expect, it } from 'vitest';

import styles from './styles.css?raw';

describe('shared unavailable button styling', () => {
  it('gives focusable aria-disabled buttons the same unavailable affordance as native disabled buttons', () => {
    const unavailableRule = styles.match(
      /button:disabled\s*,\s*button\[aria-disabled=["']true["']\]\s*\{([^}]*)\}/s,
    );

    expect(unavailableRule).not.toBeNull();
    expect(unavailableRule?.[1]).toContain('opacity: 0.6');
    expect(unavailableRule?.[1]).toContain('cursor: not-allowed');
    expect(unavailableRule?.[1]).toContain('background-color: var(--color-surface-muted)');
    expect(unavailableRule?.[1]).toContain('color: var(--color-disabled)');
  });
});
