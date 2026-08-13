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
  if (handleId === 'c-empty') return '';
  if (!handleId.startsWith('c-')) return handleId;

  const encodedParts = handleId.slice(2).split('-');
  return encodedParts.map((hex) => {
    const codePoint = parseInt(hex, 16);
    return isNaN(codePoint) ? '' : String.fromCodePoint(codePoint);
  }).join('');
}

export function decodeSourceHandleId(sourceHandleId: string): string {
  if (!sourceHandleId.startsWith('src-')) return sourceHandleId;
  return decodeHandleId(sourceHandleId.slice(4));
}

export function decodeTargetHandleId(targetHandleId: string): string {
  if (!targetHandleId.startsWith('tgt-')) return targetHandleId;
  return decodeHandleId(targetHandleId.slice(4));
}
