export function sanitizeHandleId(columnName: string): string {
  const normalized = columnName.normalize('NFKC').trim()
  const encoded = Array.from(normalized, (char) => {
    return /[A-Za-z0-9_-]/.test(char) ? char : `_${char.codePointAt(0)?.toString(16) ?? '0'}_`
  }).join('')

  return encoded || 'column'
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
