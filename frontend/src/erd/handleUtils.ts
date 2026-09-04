export function sanitizeHandleId(columnName: string): string {
  const encoded = Array.from(columnName, (char) => {
    // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}

export function parseColumnNameFromHandle(handleId: string): string {
  if (!handleId || handleId === 'c-empty' || !handleId.startsWith('c-')) return ''

  const decoded: string[] = []
  for (const part of handleId.slice(2).split('-')) {
    if (!/^[0-9a-f]{4,6}$/i.test(part)) return ''

    const codePoint = Number.parseInt(part, 16)
    if (
      codePoint > 0x10ffff ||
      (codePoint >= 0xd800 && codePoint <= 0xdfff)
    ) {
      return ''
    }
    decoded.push(String.fromCodePoint(codePoint))
  }

  return decoded.join('')
}

export function resolveColumnNameFromHandle(
  handleId: string,
  columnNames: { has(columnName: string): boolean },
): string {
  if (!handleId) return ''

  const decoded = parseColumnNameFromHandle(handleId)
  if (decoded && columnNames.has(decoded)) return decoded

  // Persisted diagrams may still carry the pre-hex raw column payload.
  return columnNames.has(handleId) ? handleId : ''
}
