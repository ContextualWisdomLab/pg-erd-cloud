export function parseColumnNameFromHandle(handleId: string): string | null {
  const match = handleId.match(/^(?:src|tgt)?-?c-(.+)$/);
  if (!match) return null;
  const encoded = match[1];
  if (encoded === 'empty') return '';

  try {
    const parts = encoded.split('-');
    return parts.map((p) => String.fromCodePoint(parseInt(p, 16))).join('');
  } catch (e) {
    return null;
  }
}

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
