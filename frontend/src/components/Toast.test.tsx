import '@testing-library/jest-dom/vitest';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { Toast } from './Toast';

describe('Toast', () => {
  it('announces a short feedback message', () => {
    render(<Toast message="DDL을 복사했습니다." />);

    const toast = screen.getByRole('status', { name: 'DDL을 복사했습니다.' });
    expect(toast).toHaveClass('toast', 'toast--info');
    expect(toast).toHaveAttribute('aria-live', 'polite');
    expect(toast).toHaveTextContent('DDL을 복사했습니다.');
  });

  it('supports success feedback styling', () => {
    render(<Toast message="공유 링크를 복사했습니다." tone="success" />);

    expect(
      screen.getByRole('status', { name: '공유 링크를 복사했습니다.' }),
    ).toHaveClass('toast--success');
  });
});
