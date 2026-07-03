import '@testing-library/jest-dom/vitest';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { Spinner } from './Spinner';

describe('Spinner', () => {
  it('announces an indeterminate loading state by default', () => {
    render(<Spinner />);

    const spinner = screen.getByRole('status', { name: '로딩 중' });
    expect(spinner).toHaveClass('spinner', 'spinner--md');
    expect(spinner).toHaveAttribute('aria-live', 'polite');
  });

  it('supports small inline loading text', () => {
    render(<Spinner size="sm" label="저장 중" />);

    expect(screen.getByRole('status', { name: '저장 중' })).toHaveClass(
      'spinner--sm',
    );
  });
});
