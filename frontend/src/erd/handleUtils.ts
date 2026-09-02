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

export function parseColumnNameFromHandle(handleId: string): string {
  if (!handleId) return '';
  const prefixRemoved = handleId.replace(/^(src|tgt)-/, '');
  if (!prefixRemoved.startsWith('c-')) return '';
  const hexParts = prefixRemoved.slice(2).split('-');
  if (hexParts.length === 1 && hexParts[0] === 'empty') return '';

  return hexParts.map(hex => {
    const codePoint = parseInt(hex, 16);
    if (isNaN(codePoint)) return '';
    return String.fromCodePoint(codePoint);
  }).join('');
}
