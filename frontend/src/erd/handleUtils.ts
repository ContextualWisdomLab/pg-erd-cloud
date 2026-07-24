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

export function decodeHandleId(encoded: string): string {
  if (encoded === 'c-empty') return ''
  if (!encoded.startsWith('c-')) return ''
  return encoded
    .slice(2)
    .split('-')
    .map((hex) => String.fromCodePoint(parseInt(hex, 16)))
    .join('')
}

export function decodeSourceHandleId(handleId: string | null | undefined): string | null {
  if (!handleId || !handleId.startsWith('src-')) return null
  return decodeHandleId(handleId.slice(4))
}

export function decodeTargetHandleId(handleId: string | null | undefined): string | null {
  if (!handleId || !handleId.startsWith('tgt-')) return null
  return decodeHandleId(handleId.slice(4))
}
