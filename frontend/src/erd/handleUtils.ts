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

export function decodeHandleId(handleId: string | null | undefined): string | null {
  if (!handleId) return null;
  const parts = handleId.split('-');
  const cIndex = parts.indexOf('c');
  if (cIndex === -1) return null;

  if (parts.length === cIndex + 2 && parts[cIndex + 1] === 'empty') {
    return '';
  }

  const hexParts = parts.slice(cIndex + 1);
  if (hexParts.length === 0) return null;

  try {
    return hexParts.map(hex => String.fromCodePoint(Number.parseInt(hex, 16))).join('');
  } catch {
    /* v8 ignore next */
    return null;
  }
}
