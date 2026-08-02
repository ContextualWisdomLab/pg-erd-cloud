export function sanitizeHandleId(columnName: string): string {
  // ⚡ Bolt: Use a for...of loop instead of Array.from to avoid intermediate array allocations
  // and reduce garbage collection (GC) overhead during high-frequency string operations.
  let encoded = ''
  let isFirst = true

  for (const char of columnName) {
    if (isFirst) {
      isFirst = false
    } else {
      encoded += '-'
    }
    // for...of only yields non-empty Unicode scalars, so codePointAt(0) is defined.
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
