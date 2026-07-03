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
  const krdsStyle = {
    backgroundColor: variant === 'primary' ? 'var(--krds-primary-color)' : 
                     variant === 'danger' ? 'var(--krds-danger-color)' : 'var(--krds-secondary-color)',
    color: variant === 'secondary' ? 'var(--krds-text-color)' : '#fff',
    borderRadius: 'var(--krds-border-radius-md)',
    padding: size === 'sm' ? 'var(--krds-spacing-sm) var(--krds-spacing-md)' :
             size === 'lg' ? 'var(--krds-spacing-lg) var(--krds-spacing-xl)' :
             'var(--krds-spacing-md) var(--krds-spacing-lg)',
    fontFamily: 'var(--krds-font-family)',
    fontSize: size === 'sm' ? 'var(--krds-font-size-sm)' :
              size === 'lg' ? 'var(--krds-font-size-lg)' : 'var(--krds-font-size-base)',
    border: 'none',
    cursor: disabled || isLoading ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
  };

  return (
    <button 
      type={type}
      className={['btn', `btn--${variant}`, `btn--${size}`, className].filter(Boolean).join(' ')}
      disabled={disabled || isLoading}
      style={{ ...krdsStyle, ...rest.style }}
      {...rest}
    >
      {children}
    </button>
  );
}
