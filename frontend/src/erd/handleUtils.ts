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

const PARSE_HANDLE_RE = /^(?:src|tgt)-c-(?:empty|([0-9a-fA-F-]+))$/;

export function parseColumnNameFromHandle(handleId: string | null | undefined): string | null {
  if (!handleId) return null;
  const match = handleId.match(PARSE_HANDLE_RE);
  if (!match) return null;
  if (!match[1]) return ''; // Matched "empty"

  const hexParts = match[1].split('-');
  try {
    return String.fromCodePoint(...hexParts.map((hex) => parseInt(hex, 16)));
  } catch (e) {
    return null;
  }
}
