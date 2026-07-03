import type { HTMLAttributes } from 'react';

export type SpinnerSize = 'sm' | 'md';

interface SpinnerProps extends HTMLAttributes<HTMLSpanElement> {
  label?: string;
  size?: SpinnerSize;
}

export function Spinner({
  label = '로딩 중',
  size = 'md',
  className,
  ...rest
}: SpinnerProps) {
  const classes = ['spinner', `spinner--${size}`, className]
    .filter(Boolean)
    .join(' ');

  return (
    <span role="status" aria-label={label} aria-live="polite" className={classes} {...rest}>
      <span aria-hidden="true" className="spinner__mark" />
    </span>
  );
}
