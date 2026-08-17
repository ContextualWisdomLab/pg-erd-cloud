export function sanitizeHandleId(columnName: string): string {
  // Optimization: Replacing Array.from(...).join('-') with a native for-loop
  // avoids intermediate array allocations and reduces garbage collection (GC) overhead.
  // The loop correctly handles Unicode scalar values (including surrogate pairs).
  let encoded = ''
  for (let i = 0; i < columnName.length; ) {
    const codePoint = columnName.codePointAt(i)!
    if (i > 0) {
      encoded += '-'
    }
    encoded += codePoint.toString(16).padStart(4, '0')
    i += codePoint > 0xffff ? 2 : 1
  }

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
