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

export function parseColumnNameFromHandle(handleId: string | undefined | null): string | null {
  if (!handleId || handleId.length > 512) return null;

  const encoded = handleId.startsWith('src-') || handleId.startsWith('tgt-')
    ? handleId.slice(4)
    : handleId;
  if (!encoded.startsWith('c-')) return null;

  const codePoints = encoded.slice(2);
  if (codePoints === 'empty') return '';

  const parts = codePoints.split('-');
  if (!parts.every((part) => /^[0-9a-f]{4,6}$/i.test(part))) return null;

  try {
    return parts.map((part) => String.fromCodePoint(Number.parseInt(part, 16))).join('');
  } catch {
    return null;
  }
}
