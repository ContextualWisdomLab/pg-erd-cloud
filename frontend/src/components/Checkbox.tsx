import React, { InputHTMLAttributes, forwardRef, useId } from 'react';

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
  error?: boolean;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, error, className = '', id, ...props }, ref) => {
    const defaultId = useId();
    const inputId = id || defaultId;
    
    return (
      <div className={`krds-checkbox-wrapper ${className}`} style={{ display: 'flex', alignItems: 'center', gap: 'var(--krds-spacing-sm)' }}>
        <input
          ref={ref}
          type="checkbox"
          id={inputId}
          aria-invalid={error ? 'true' : 'false'}
          style={{
            width: '16px',
            height: '16px',
            cursor: props.disabled ? 'not-allowed' : 'pointer',
            accentColor: 'var(--krds-primary-color)'
          }}
          {...props}
        />
        <label
          htmlFor={inputId}
          style={{
            fontSize: 'var(--krds-font-size-base)',
            color: props.disabled ? '#a5adba' : 'var(--krds-text-color)',
            cursor: props.disabled ? 'not-allowed' : 'pointer'
          }}
        >
          {label}
        </label>
      </div>
    );
  }
);

Checkbox.displayName = 'Checkbox';
