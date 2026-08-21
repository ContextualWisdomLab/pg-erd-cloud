export function sanitizeHandleId(columnName: string): string {
  const encoded = Array.from(columnName, (char) => {
    // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
}

/**
 * Decodes a column handle suffix created by {@link sanitizeHandleId}.
 *
 * Returns `null` for malformed handles so callers can preserve compatibility
 * with legacy handles that stored the column name without encoding.
 */
export function decodeHandleId(handleId: string): string | null {
  if (!handleId.startsWith('c-')) return null

  const encoded = handleId.slice(2)
  if (encoded === 'empty') return ''

  const parts = encoded.split('-')
  const codePoints = parts.map((part) => Number.parseInt(part, 16))
  if (
    parts.some(
      (part, index) =>
        !/^[0-9a-f]+$/i.test(part) ||
        codePoints[index] > 0x10ffff ||
        (codePoints[index] >= 0xd800 && codePoints[index] <= 0xdfff),
    )
  ) {
    return null
  }

  return String.fromCodePoint(...codePoints)
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
