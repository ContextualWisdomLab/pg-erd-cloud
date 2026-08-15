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
  if (parts.length < 2) return null;

  if (parts[0] === 'src' || parts[0] === 'tgt') {
    parts.shift();
  }

  if (parts[0] !== 'c') return null;

  if (parts.length === 2 && parts[1] === 'empty') return '';

  const hexCodes = parts.slice(1);
  try {
    return hexCodes.map(hex => String.fromCodePoint(parseInt(hex, 16))).join('');
  } catch (e) {
    return null;
  }
}
