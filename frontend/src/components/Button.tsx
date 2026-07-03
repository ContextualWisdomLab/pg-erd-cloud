import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost';
export type ButtonSize = 'sm' | 'md';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
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
  ...rest
}: ButtonProps) {
  const classes = ['btn', `btn--${variant}`, `btn--${size}`, className]
    .filter(Boolean)
    .join(' ');

  return (
    <button type={type} className={classes} {...rest}>
      {children}
    </button>
  );
}
