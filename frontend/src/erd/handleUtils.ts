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

  if (!encoded.startsWith('c-')) {
    // For tests or legacy handles that might not have the c- prefix encoding
    return encoded;
  }
  encoded = encoded.slice(2);

  if (encoded === 'empty') return '';
  if (!encoded) return '';

  try {
    return encoded.split('-').map(hex => String.fromCodePoint(parseInt(hex, 16))).join('');
  } catch (e) {
    return null;
  }
}
