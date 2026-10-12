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

export function parseHandleId(handleId: string): string {
  if (!handleId || handleId === 'c-empty') return '';
  if (handleId.startsWith('c-')) {
    const encoded = handleId.slice(2);
    if (!encoded) return '';
    try {
      return String.fromCodePoint(...encoded.split('-').map(hex => parseInt(hex, 16)));
    } catch {
      return handleId;
    }
  }
  return handleId;
}
