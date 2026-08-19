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

  let encoded = handleId;
  if (encoded.startsWith('src-')) encoded = encoded.slice(4);
  else if (encoded.startsWith('tgt-')) encoded = encoded.slice(4);

  if (encoded === 'c-empty') return '';
  if (!encoded.startsWith('c-')) return null;

  const parts = encoded.slice(2).split('-');
  if (!parts.every((part) => /^[0-9a-f]{4,6}$/i.test(part))) return null;
  try {
    return parts.map(p => String.fromCodePoint(parseInt(p, 16))).join('');
  } catch {
    return null;
  }
}
