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
  const parts = handleId.split('-');
  if (parts.length < 3 || parts[1] !== 'c') {
    return null;
  }

  const encoded = parts.slice(2).join('-');
  if (encoded === 'empty') return '';

  try {
    return encoded
      .split('-')
      .map((hex) => String.fromCodePoint(parseInt(hex, 16)))
      .join('');
  } catch (e) {
    return null;
  }
}
