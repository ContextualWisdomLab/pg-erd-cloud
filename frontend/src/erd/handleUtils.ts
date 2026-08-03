const HANDLE_ID_PATTERN = /^(?:(?:src|tgt)-)?c-(.+)$/;
const HEX_CODE_POINT_PATTERN = /^[0-9a-f]{4,6}$/i;

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

export function decodeHandleId(handleId: string | null | undefined): string | null {
  if (!handleId) return null

  const match = HANDLE_ID_PATTERN.exec(handleId)
  if (!match) return null

  const encoded = match[1]
  if (encoded === 'empty') return ''

  const decoded: string[] = []
  for (const hex of encoded.split('-')) {
    if (!HEX_CODE_POINT_PATTERN.test(hex)) return null

    const codePoint = Number.parseInt(hex, 16)
    const canonicalHex = codePoint.toString(16).padStart(4, '0')
    if (hex.toLowerCase() !== canonicalHex || codePoint > 0x10ffff) {
      return null
    }

    decoded.push(String.fromCodePoint(codePoint))
  }

  return decoded.join('')
}
