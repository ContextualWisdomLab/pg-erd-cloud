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
  if (handleId === 'c-empty' || !handleId.startsWith('c-')) return '';
  const hexParts = handleId.slice(2).split('-');
  return String.fromCodePoint(...hexParts.map((hex) => parseInt(hex, 16)));
}

export function decodeSourceHandleId(handleId: string): string {
  if (!handleId.startsWith('src-')) return '';
  const decoded = decodeHandleId(handleId.slice(4));
  return decoded || handleId.slice(4); // fallback for tests using unencoded 'src-user_id'
}

export function decodeTargetHandleId(handleId: string): string {
  if (!handleId.startsWith('tgt-')) return '';
  const decoded = decodeHandleId(handleId.slice(4));
  return decoded || handleId.slice(4); // fallback for tests using unencoded 'tgt-id'
}
