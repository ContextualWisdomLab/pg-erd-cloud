import type { HTMLAttributes } from 'react';

export type ToastTone = 'info' | 'success';

interface ToastProps extends HTMLAttributes<HTMLDivElement> {
  message: string;
  tone?: ToastTone;
}

export function Toast({
  message,
  tone = 'info',
  className,
  ...rest
}: ToastProps) {
  const classes = ['toast', `toast--${tone}`, className]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      role="status"
      aria-label={message}
      aria-live="polite"
      className={classes}
      {...rest}
    >
      {message}
    </div>
  );
}
