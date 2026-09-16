export function sanitizeHandleId(columnName: string): string {
  // ⚡ Bolt: Use for...of loop instead of Array.from(string).map().join('-')
  // to prevent intermediate array allocations and GC pauses in the ERD hot paths.
  let encoded = ''
  let isFirst = true
  for (const char of columnName) {
    if (!isFirst) {
      encoded += '-'
    }
    // char.codePointAt(0) is defined for valid strings in a for...of loop
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
