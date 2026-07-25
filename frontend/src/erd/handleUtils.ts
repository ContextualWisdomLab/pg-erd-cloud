export function parseColumnNameFromHandle(handleId: string | null | undefined): string | null {
  if (!handleId) return null;
  const match = handleId.match(/^(?:src-|tgt-)?c-(.+)$/);
  if (!match) return null;
  const encoded = match[1];
  if (encoded === 'empty') return '';
  return encoded.split('-').map(hex => String.fromCodePoint(parseInt(hex, 16))).join('');
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
