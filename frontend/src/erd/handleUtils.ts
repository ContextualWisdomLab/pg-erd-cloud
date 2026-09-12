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

export function decodeHandleId(handleId: string): string {
  if (!handleId || handleId.endsWith('-c-empty') || handleId === 'c-empty') {
    return '';
  }
  let encodedPart = handleId;
  if (handleId.startsWith('src-c-')) {
    encodedPart = handleId.slice(6);
  } else if (handleId.startsWith('tgt-c-')) {
    encodedPart = handleId.slice(6);
  } else if (handleId.startsWith('c-')) {
    encodedPart = handleId.slice(2);
  }

  const parts = encodedPart.split('-');
  return parts.map(hex => String.fromCodePoint(parseInt(hex, 16))).join('');
}
