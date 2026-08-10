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

  let idPart = handleId;
  if (idPart.startsWith('src-')) {
    idPart = idPart.slice(4);
  } else if (idPart.startsWith('tgt-')) {
    idPart = idPart.slice(4);
  }

  if (idPart === 'c-empty') {
    return '';
  }

  if (!idPart.startsWith('c-')) {
    // Fallback for tests or legacy unencoded handles
    return idPart;
  }

  const encoded = idPart.slice(2);
  if (!encoded) return '';

  try {
    return encoded.split('-').map(hex => String.fromCodePoint(parseInt(hex, 16))).join('');
  } catch (e) {
    return null;
  }
}
