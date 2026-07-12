export function sanitizeHandleId(columnName: string): string {
  const encoded = Array.from(columnName, (char) => {
    return char.codePointAt(0)?.toString(16).padStart(4, '0') ?? '0000'
  }).join('-')

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
