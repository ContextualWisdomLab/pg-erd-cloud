export function sanitizeHandleId(columnName: string): string {
  // Use for...of loop instead of Array.from to prevent intermediate array
  // allocations and reduce GC pressure in this hot path for ERD rendering
  let encoded = ''
  let isFirst = true
  for (const char of columnName) {
    // for...of on a string yields Unicode scalars, so codePointAt(0) is defined.
    const hex = char.codePointAt(0)!.toString(16).padStart(4, '0')
    if (isFirst) {
      encoded += hex
      isFirst = false
    } else {
      encoded += '-' + hex
    }
  }

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
