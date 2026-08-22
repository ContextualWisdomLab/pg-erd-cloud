export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty'

  let encoded = ''
  let first = true
  for (const char of columnName) {
    if (first) {
      first = false
    } else {
      encoded += '-'
    }
    // ⚡ Bolt: Use for...of loop instead of Array.from().join('-') in hot path
    // to prevent intermediate array allocations and reduce garbage collection pressure.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0')
  }

  return `c-${encoded}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
