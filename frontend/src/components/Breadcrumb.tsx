import React from 'react';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[];
  className?: string;
}

export const Breadcrumb: React.FC<BreadcrumbProps> = ({ items, className = '' }) => {
  return (
    <nav aria-label="브레드크럼" className={`krds-breadcrumb ${className}`}>
      <ol style={{ display: 'flex', listStyle: 'none', padding: 0, margin: 0, gap: 'var(--krds-spacing-xs)', alignItems: 'center' }}>
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          
          return (
            <li key={index} style={{ display: 'flex', alignItems: 'center', gap: 'var(--krds-spacing-xs)' }}>
              {isLast ? (
                <span
                  aria-current="page"
                  style={{
                    color: 'var(--krds-text-color)',
                    fontWeight: 600,
                    fontSize: 'var(--krds-font-size-sm)'
                  }}
                >
                  {item.label}
                </span>
              ) : (
                <a
                  href={item.href || '#'}
                  style={{
                    color: 'var(--krds-primary-color)',
                    textDecoration: 'none',
                    fontSize: 'var(--krds-font-size-sm)'
                  }}
                >
                  {item.label}
                </a>
              )}
              {!isLast && (
                <span aria-hidden="true" style={{ color: '#a5adba', fontSize: 'var(--krds-font-size-sm)' }}>
                  /
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

export default Breadcrumb;
