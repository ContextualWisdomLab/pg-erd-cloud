import React, { InputHTMLAttributes, forwardRef, useId } from 'react';

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  helperText?: string;
  error?: boolean;
  required?: boolean;
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  ({ label, helperText, error, required, className = '', id, ...props }, ref) => {
    const defaultId = useId();
    const inputId = id || defaultId;
    const helperId = `${inputId}-helper`;
    
    return (
      <div className={`krds-text-input-group ${className}`} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--krds-spacing-xs)', marginBottom: 'var(--krds-spacing-md)' }}>
        <label htmlFor={inputId} style={{ fontSize: 'var(--krds-font-size-sm)', fontWeight: 600, color: 'var(--krds-text-color)' }}>
          {label} {required && <span aria-hidden="true" style={{ color: 'var(--krds-danger-color)' }}>*</span>}
        </label>
        <input
          ref={ref}
          id={inputId}
          className="krds-text-input"
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={helperText ? helperId : undefined}
          required={required}
          style={{
            padding: 'var(--krds-spacing-sm) var(--krds-spacing-md)',
            borderRadius: 'var(--krds-border-radius-sm)',
            border: `1px solid ${error ? 'var(--krds-danger-color)' : '#dfe1e6'}`,
            fontSize: 'var(--krds-font-size-base)',
            fontFamily: 'var(--krds-font-family)',
            outline: 'none',
          }}
          {...props}
        />
        {helperText && (
          <span
            id={helperId}
            style={{
              fontSize: 'var(--krds-font-size-sm)',
              color: error ? 'var(--krds-danger-color)' : '#6b778c'
            }}
          >
            {helperText}
          </span>
        )}
      </div>
    );
  }
);

TextInput.displayName = 'TextInput';
