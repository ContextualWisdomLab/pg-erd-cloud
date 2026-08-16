export function sanitizeHandleId(columnName: string): string {
  // OPTIMIZATION: Avoid intermediate array allocation to reduce GC pressure during large ERD renders
  let encoded = ''
  for (const char of columnName) {
    if (encoded) encoded += '-'
    // for...of on a string yields non-empty Unicode scalars, so codePointAt(0) is defined.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0')
  }

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
