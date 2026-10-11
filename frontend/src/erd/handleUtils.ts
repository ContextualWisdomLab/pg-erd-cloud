export function sanitizeHandleId(columnName: string): string {
  // ⚡ Bolt: Use for...of instead of Array.from to eliminate intermediate array allocations
  // and reduce garbage collection pressure in high-frequency rendering paths.
  let encoded = ''
  let isFirst = true

  for (const char of columnName) {
    if (!isFirst) {
      encoded += '-'
    }
    isFirst = false
    // for...of natively handles Unicode surrogate pairs, so codePointAt(0) is defined.
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
