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

export function parseColumnNameFromHandle(handleId: string): string | null {
  if (!handleId) return null;
  const match = handleId.match(/^(src|tgt)-c-(.+)$/);
  if (!match) return null;
  const encoded = match[2];
  if (encoded === 'empty') return '';
  const codePoints = encoded.split('-').map((code) => {
    if (!/^[0-9a-f]{1,6}$/i.test(code)) return null;
    const codePoint = Number.parseInt(code, 16);
    if (codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) {
      return null;
    }
    return codePoint;
  });
  if (codePoints.some((codePoint) => codePoint === null)) return null;
  return codePoints.map((codePoint) => String.fromCodePoint(codePoint!)).join('');
}
