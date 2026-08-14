export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty'

  let encoded = ''
  let isFirst = true
  for (let i = 0; i < columnName.length; i++) {
    const cp = columnName.codePointAt(i)
    if (cp === undefined) continue

    if (cp > 0xffff) i++ // Handle surrogate pairs

    if (isFirst) {
      isFirst = false
    } else {
      encoded += '-'
    }

    const hex = cp.toString(16)
    if (hex.length < 4) {
      encoded += '0000'.substring(0, 4 - hex.length) + hex
    } else {
      encoded += hex
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
