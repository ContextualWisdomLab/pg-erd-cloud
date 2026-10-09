export function sanitizeHandleId(columnName: string): string {
  // ⚡ Bolt: Use for...of string iteration to avoid Array.from intermediate array allocations
  // and GC pressure during high-frequency graph edge calculations.
  let encoded = ''
  for (const char of columnName) {
    if (encoded) encoded += '-'
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
