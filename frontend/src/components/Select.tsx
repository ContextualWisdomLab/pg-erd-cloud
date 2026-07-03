import React, { SelectHTMLAttributes, forwardRef, useId } from 'react';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  helperText?: string;
  error?: boolean;
  required?: boolean;
  options: { label: string; value: string | number }[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, helperText, error, required, options, className = '', id, ...props }, ref) => {
    const defaultId = useId();
    const selectId = id || defaultId;
    const helperId = `${selectId}-helper`;
    
    return (
      <div className={`krds-select-group ${className}`} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--krds-spacing-xs)', marginBottom: 'var(--krds-spacing-md)' }}>
        <label htmlFor={selectId} style={{ fontSize: 'var(--krds-font-size-sm)', fontWeight: 600, color: 'var(--krds-text-color)' }}>
          {label} {required && <span aria-hidden="true" style={{ color: 'var(--krds-danger-color)' }}>*</span>}
        </label>
        <select
          ref={ref}
          id={selectId}
          className="krds-select"
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
            backgroundColor: '#fff',
            cursor: props.disabled ? 'not-allowed' : 'pointer',
          }}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
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

Select.displayName = 'Select';
