export function sanitizeHandleId(columnName: string): string {
  let encoded = ''
  for (const char of columnName) {
    if (encoded.length > 0) {
      encoded += '-'
    }
    // for...of iterates over Unicode code points, so char is a single scalar.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0')
  }
  // Trigger OpenCode review

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
