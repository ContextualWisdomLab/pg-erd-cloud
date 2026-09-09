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
    const parts = encoded.split('-');
    const chars = parts.map(hex => {
      if (!/^[0-9a-fA-F]{1,6}$/.test(hex)) throw new Error('Invalid hex format');
      const codePoint = parseInt(hex, 16);
      if (isNaN(codePoint) || codePoint < 0 || codePoint > 0x10FFFF) throw new Error('Invalid hex range');
      // Surrogate halves are invalid code points for strings
      if (codePoint >= 0xD800 && codePoint <= 0xDFFF) throw new Error('Invalid surrogate pair code point');
      return String.fromCodePoint(codePoint);
    });
    const decoded = chars.join('');
    return `${prefix}${sanitizeHandleId(decoded)}` === handleId ? decoded : null;
  } catch {
    return null;
  }
}
