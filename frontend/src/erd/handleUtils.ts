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
  if (!['src', 'tgt'].includes(parts[0]) || parts[1] !== 'c' || parts.length < 3) {
    return null;
  }

  const encodedParts = parts.slice(2);
  if (encodedParts.length === 1 && encodedParts[0] === 'empty') return '';
  if (!encodedParts.every((hex) => /^[0-9a-f]{4,6}$/i.test(hex))) return null;

  try {
    return encodedParts
      .map((hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
      .join('');
  } catch {
    return null;
  }
}
