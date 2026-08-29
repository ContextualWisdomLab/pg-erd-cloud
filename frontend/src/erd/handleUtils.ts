export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty'
  let encoded = ''
  let isFirst = true
  for (const char of columnName) {
    if (!isFirst) {
      encoded += '-'
    } else {
      isFirst = false
    }
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
