import React from 'react';

export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  onPageChange,
  className = ''
}) => {
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

  return (
    <nav aria-label="페이지 이동" className={`krds-pagination ${className}`} style={{ display: 'flex', justifyContent: 'center', gap: 'var(--krds-spacing-xs)' }}>
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        aria-label="이전 페이지"
        style={{
          padding: 'var(--krds-spacing-xs) var(--krds-spacing-sm)',
          border: '1px solid #dfe1e6',
          backgroundColor: '#fff',
          borderRadius: 'var(--krds-border-radius-sm)',
          cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
          color: currentPage === 1 ? '#a5adba' : 'var(--krds-text-color)',
        }}
      >
        이전
      </button>
      
      <div style={{ display: 'flex', gap: '4px' }}>
        {pages.map((page) => (
          <button
            key={page}
            onClick={() => onPageChange(page)}
            aria-current={currentPage === page ? 'page' : undefined}
            style={{
              padding: 'var(--krds-spacing-xs) var(--krds-spacing-sm)',
              border: currentPage === page ? '1px solid var(--krds-primary-color)' : '1px solid #dfe1e6',
              backgroundColor: currentPage === page ? 'var(--krds-primary-color)' : '#fff',
              color: currentPage === page ? '#fff' : 'var(--krds-text-color)',
              borderRadius: 'var(--krds-border-radius-sm)',
              cursor: 'pointer',
            }}
          >
            {page}
          </button>
        ))}
      </div>

      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        aria-label="다음 페이지"
        style={{
          padding: 'var(--krds-spacing-xs) var(--krds-spacing-sm)',
          border: '1px solid #dfe1e6',
          backgroundColor: '#fff',
          borderRadius: 'var(--krds-border-radius-sm)',
          cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
          color: currentPage === totalPages ? '#a5adba' : 'var(--krds-text-color)',
        }}
      >
        다음
      </button>
    </nav>
  );
};

export default Pagination;
