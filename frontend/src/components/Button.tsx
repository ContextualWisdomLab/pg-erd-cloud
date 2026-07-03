import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  children: ReactNode;
}

/**
 * Reusable button primitive.
 *
 * Encodes the "PG ERD Button" component defined in the Figma design system
 * (variants: Primary / Secondary / Ghost). Visual styles live in
 * `frontend/src/styles.css` under the `.btn` classes and are driven by the
 * `--color-action-primary` design token. See docs/design-system/README.md.
 *
 * `type` defaults to "button" so a Button placed inside a <form> does not
 * accidentally submit it; pass `type="submit"` explicitly for submit actions.
 */
export function Button({
  variant = 'secondary',
  size = 'md',
  type = 'button',
  className,
  children,
  disabled,
  isLoading,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={['btn', `btn--${variant}`, `btn--${size}`, className].filter(Boolean).join(' ')}
      disabled={disabled || isLoading}
      {...rest}
    >
      {children}
    </button>
  );
}
