export function sanitizeHandleId(columnName: string): string {
  // Optimize string generation to avoid intermediate array allocations
  // from Array.from and .join('-') by using a direct string builder.
  let encoded = ''
  let isFirst = true
  for (const char of columnName) {
    if (isFirst) {
      isFirst = false
    } else {
      encoded += '-'
    }
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
