import { describe, expect, it } from 'vitest';

import unavailableButtonStyles from './button-states.css?raw';
import entrypoint from './main.tsx?raw';

describe('shared unavailable button styling', () => {
  it('gives focusable aria-disabled buttons the unavailable affordance and loads it globally', () => {
    const unavailableRule = unavailableButtonStyles.match(
      /button\[aria-disabled=["']true["']\]\s*\{([^}]*)\}/s,
    );

    expect(unavailableRule).not.toBeNull();
    expect(unavailableRule?.[1]).toContain('opacity: 0.6');
    expect(unavailableRule?.[1]).toContain('cursor: not-allowed');
    expect(unavailableRule?.[1]).toContain('background-color: var(--color-surface-muted)');
    expect(unavailableRule?.[1]).toContain('color: var(--color-disabled)');
    expect(entrypoint).toContain("import './button-states.css'");
  });
});
