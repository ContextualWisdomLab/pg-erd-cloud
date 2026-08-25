export function sanitizeHandleId(columnName: string): string {
  // ⚡ Bolt: Use a for...of loop instead of Array.from(columnName).join('-')
  // to avoid allocating an intermediate array and reduce GC pressure for hot paths.
  let encoded = ''
  let isFirst = true
  for (const char of columnName) {
    if (!isFirst) {
      encoded += '-'
    }
    // for...of over strings natively yields non-empty Unicode scalars, so codePointAt(0) is always defined.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0')
    isFirst = false
  }

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
