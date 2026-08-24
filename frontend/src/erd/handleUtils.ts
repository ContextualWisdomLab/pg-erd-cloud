export function sanitizeHandleId(columnName: string): string {
  if (columnName.length > 1000) return 'c-empty';
  const encoded = Array.from(columnName, (char) => {
    // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  if (columnName.length > 1000) return 'src-c-empty';
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  if (columnName.length > 1000) return 'tgt-c-empty';
  return `tgt-${sanitizeHandleId(columnName)}`
}

export function parseColumnNameFromHandle(handle: string | null | undefined): string | null {
  if (handle && handle.length > 10000) return null;
  if (!handle) return null;
  // Handle can be src-c-... or tgt-c-... or c-...
  let encoded: string | null = null;
  if (handle.startsWith('src-c-') || handle.startsWith('tgt-c-')) {
    encoded = handle.slice(6);
  } else if (handle.startsWith('c-')) {
    encoded = handle.slice(2);
  }

  if (encoded === null) return null;
  if (encoded === 'empty') return '';

  try {
    return encoded.split('-').map(hex => String.fromCodePoint(parseInt(hex, 16))).join('');
  } catch (e) {
    return null;
  }
}
