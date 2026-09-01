export function sanitizeHandleId(columnName: string): string {
  let encoded = ''
  let first = true
  for (const char of columnName) {
    if (!first) {
      encoded += '-'
    }
    first = false
    // for...of iterates over Unicode code points, so char is a single scalar.
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
