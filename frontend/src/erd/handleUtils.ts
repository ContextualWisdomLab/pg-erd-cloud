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

export function parseColumnNameFromHandle(handle: string | null | undefined): string | null {
  if (!handle) return null;
  const prefixMatch = handle.match(/^(src|tgt)-c-(.*)$/);
  if (!prefixMatch) return null;
  const encoded = prefixMatch[2];
  if (encoded === 'empty' || !encoded) return '';

  try {
    const chars = encoded.split('-');
    return chars.map(c => String.fromCodePoint(parseInt(c, 16))).join('');
  } catch (e) {
    return null;
  }
}
