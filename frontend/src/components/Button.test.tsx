import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { Button } from './Button';

describe('Button', () => {
  it('renders its children as the accessible name', () => {
    render(<Button>저장</Button>);
    expect(screen.getByRole('button', { name: '저장' })).toBeInTheDocument();
  });

  it('applies variant and size classes', () => {
    render(
      <Button variant="primary" size="sm">
        Primary
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Primary' });
    expect(button).toHaveClass('btn', 'btn--primary', 'btn--sm');
  });

  it('defaults to type="button" to avoid accidental form submission', () => {
    render(<Button>Safe</Button>);
    expect(screen.getByRole('button', { name: 'Safe' })).toHaveAttribute(
      'type',
      'button',
    );
  });

  it('forwards an explicit submit type', () => {
    render(
      <Button type="submit" variant="primary">
        Submit
      </Button>,
    );
    expect(screen.getByRole('button', { name: 'Submit' })).toHaveAttribute(
      'type',
      'submit',
    );
  });

  it('invokes onClick when enabled', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    await userEvent.click(screen.getByRole('button', { name: 'Click' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('does not invoke onClick when disabled', async () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        Disabled
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Disabled' });
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('merges a caller-supplied className', () => {
    render(<Button className="custom">Merged</Button>);
    expect(screen.getByRole('button', { name: 'Merged' })).toHaveClass(
      'btn',
      'custom',
    );
  });
});
