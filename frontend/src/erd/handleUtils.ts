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
  let encoded = handle;
  if (encoded.startsWith('src-')) {
    encoded = encoded.slice(4);
  } else if (encoded.startsWith('tgt-')) {
    encoded = encoded.slice(4);
  }

  if (!encoded.startsWith('c-')) return null;
  encoded = encoded.slice(2);

  if (encoded === 'empty') return '';

  try {
    return encoded.split('-').map(hex => String.fromCodePoint(parseInt(hex, 16))).join('');
  } catch (e) {
    return null;
  }
}
