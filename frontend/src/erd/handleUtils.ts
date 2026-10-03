/** Encode a column name as a React Flow-safe handle identifier. */
export function sanitizeHandleId(columnName: string): string {
  let encoded = '';
  for (const char of columnName) {
    if (encoded) encoded += '-';
    // for...of only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0');
  }

  return `c-${encoded || 'empty'}`
}

/** Build the source-side handle identifier for a column. */
export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

/** Build the target-side handle identifier for a column. */
export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
