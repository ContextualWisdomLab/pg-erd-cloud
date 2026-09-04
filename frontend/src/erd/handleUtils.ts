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

export function parseColumnNameFromHandle(handleId: string | null | undefined, direction?: 'src' | 'tgt'): string | null {
  if (!handleId) return null;
  const match = handleId.match(/^(src|tgt)-c-([0-9a-f-]+|empty)$/);
  if (!match) return null;
  const parsedDirection = match[1];
  if (direction && parsedDirection !== direction) return null;
  const encoded = match[2];
  if (encoded === 'empty') return '';
  try {
    const decoded = encoded.split('-').map((hex) => {
      if (!/^[0-9a-f]{4,6}$/.test(hex)) throw new Error('Invalid hex format');
      const codePoint = parseInt(hex, 16);
      if (codePoint > 0x10FFFF) throw new Error('Invalid code point');
      return String.fromCodePoint(codePoint);
    }).join('');
    // Verify canonical re-encoding to reject padded or noncanonical hex casing.
    if (sanitizeHandleId(decoded) !== `c-${encoded}`) return null;
    return decoded;
  } catch (e) {
    return null;
  }
}
