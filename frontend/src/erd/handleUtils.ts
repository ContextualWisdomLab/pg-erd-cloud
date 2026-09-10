export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty'

  // ⚡ Bolt: Use for...of instead of Array.from(string).map().join() to eliminate
  // intermediate array allocations and GC pressure in highly-frequent column handle lookups.
  let encoded = ''
  for (const char of columnName) {
    if (encoded) encoded += '-'
    // for...of on strings yields unicode scalars correctly
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
