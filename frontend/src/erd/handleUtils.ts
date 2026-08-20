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
  if (!handleId) return null;
  const parts = handleId.split('-');
  if (parts.length < 3 || (parts[0] !== 'src' && parts[0] !== 'tgt') || parts[1] !== 'c') return null;
  const encoded = parts.slice(2);
  if (encoded.length === 1 && encoded[0] === 'empty') return '';
  if (!encoded.every((code) => /^[0-9a-f]{4,6}$/.test(code))) return null;
  try {
    const codePoints = encoded.map((code) => parseInt(code, 16));
    if (codePoints.some((code) => code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff))) return null;
    return codePoints.map((code) => String.fromCodePoint(code)).join('');
  } catch {
    return null;
  }
}
