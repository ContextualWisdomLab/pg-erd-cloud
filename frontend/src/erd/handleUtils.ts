export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty'

  // ⚡ Bolt: Use for...of instead of Array.from to prevent intermediate array allocations
  // and reduce garbage collection pressure in hot paths during ERD graph processing.
  const parts = []
  for (const char of columnName) {
    // for...of on strings yields non-empty Unicode scalars, so codePointAt(0) is defined.
    parts.push(char.codePointAt(0)!.toString(16).padStart(4, '0'))
  }

  return `c-${parts.join('-')}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
