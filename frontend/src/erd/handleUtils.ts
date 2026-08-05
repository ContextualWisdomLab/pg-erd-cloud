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
  const parts = handleId.split('-');
  const startIndex = parts[0] === 'src' || parts[0] === 'tgt' ? 2 : 1;

  if (parts.length <= startIndex || parts[startIndex] === 'empty') {
    return '';
  }

  try {
    return String.fromCodePoint(...parts.slice(startIndex).map((hex) => parseInt(hex, 16)));
  } catch {
    return null;
  }
}
