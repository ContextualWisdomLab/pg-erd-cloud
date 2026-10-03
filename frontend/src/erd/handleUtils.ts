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


export function decodeHandleId(handleId: string | null | undefined): string | undefined {
  if (!handleId || typeof handleId !== 'string') return undefined;

  let encodedPart = "";
  if (handleId.startsWith('src-c-')) {
    encodedPart = handleId.substring(6);
  } else if (handleId.startsWith('tgt-c-')) {
    encodedPart = handleId.substring(6);
  } else {
    return undefined;
  }

  if (encodedPart === 'empty') return "";

  try {
    return encodedPart.split('-').map(hex => String.fromCodePoint(parseInt(hex, 16))).join('');
  } catch (e) {
    return undefined;
  }
}
