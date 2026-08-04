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

export function parseColumnNameFromHandle(handleId: string | undefined | null): string | null {
  if (!handleId) return null;

  const prefixMatch = handleId.match(/^(?:src-|tgt-)?c-(.*)$/);
  if (!prefixMatch) return null;

  const encoded = prefixMatch[1];
  if (encoded === 'empty') return '';

  try {
    const chars = encoded.split('-').map(hex => String.fromCodePoint(parseInt(hex, 16)));
    return chars.join('');
  } catch (e) {
    return null;
  }
}
