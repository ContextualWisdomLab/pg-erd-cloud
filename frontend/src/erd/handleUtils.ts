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

export function parseColumnNameFromHandle(handleId: string | null | undefined): string | null {
  if (!handleId) return null

  const match = handleId.match(/^(src|tgt)-c-(empty|[0-9a-f]{4,6}(?:-[0-9a-f]{4,6})*)$/)
  if (!match) return null

  const [, direction, encoded] = match
  if (encoded === 'empty') return ''

  const chars: string[] = []
  for (const hex of encoded.split('-')) {
    const codePoint = Number.parseInt(hex, 16)
    if (codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) {
      return null
    }
    chars.push(String.fromCodePoint(codePoint))
  }

  const columnName = chars.join('')
  const canonicalHandle = direction === 'src'
    ? sourceColumnHandleId(columnName)
    : targetColumnHandleId(columnName)
  return canonicalHandle === handleId ? columnName : null
}
