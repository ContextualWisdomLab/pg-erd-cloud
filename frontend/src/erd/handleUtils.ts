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

export function decodeHandleId(handleId: string): string | null {
  if (handleId === 'c-empty') return '';
  if (!handleId.startsWith('c-')) return null;
  const parts = handleId.slice(2).split('-');
  try {
    return parts.map(part => String.fromCodePoint(parseInt(part, 16))).join('');
  /* v8 ignore next */
  } catch {
  /* v8 ignore next */
    return null;
  /* v8 ignore next */
  }
}

export function decodeSourceHandleId(handleId: string): string | null {
  if (!handleId.startsWith('src-')) return null;
  return decodeHandleId(handleId.slice(4));
}

export function decodeTargetHandleId(handleId: string): string | null {
  if (!handleId.startsWith('tgt-')) return null;
  return decodeHandleId(handleId.slice(4));
}
