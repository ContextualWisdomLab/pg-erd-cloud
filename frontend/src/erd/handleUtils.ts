export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty'

  let encoded = ''
  let first = true
  for (const char of columnName) {
    if (!first) encoded += '-'
    // for...of on strings iterates over Unicode code points, so char is a full scalar.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0')
    first = false
  }

  return `c-${encoded}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
