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

export function parseHandleId(handleId: string | null | undefined, prefix: string): string | null {
  if (!handleId || !handleId.startsWith(`${prefix}c-`)) return null;
  const encoded = handleId.slice(prefix.length + 2);
  if (encoded === 'empty' || !encoded) return "";

  try {
    return encoded.split('-').map(hex => {
      const codePoint = parseInt(hex, 16);
      if (isNaN(codePoint)) throw new Error('Invalid hex');
      return String.fromCodePoint(codePoint);
    }).join('');
  } catch (e) {
    return null;
  }
}
