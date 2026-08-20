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

const HEX_CHUNK_RE = /^[0-9a-f]{4,6}$/

/** Decode a canonical column handle and reject malformed or out-of-range input. */
export function decodeHandleId(handleId: string | null | undefined): string | null {
  if (!handleId || handleId.length > 10000) return null;

  const parts = handleId.split('-');
  let payloadIndex = -1;
  if (parts[0] === 'c') {
    payloadIndex = 1;
  } else if ((parts[0] === 'src' || parts[0] === 'tgt') && parts[1] === 'c') {
    payloadIndex = 2;
  }
  if (payloadIndex === -1) return null;
  if (parts.length === payloadIndex + 1 && parts[payloadIndex] === 'empty') return '';

  const hexParts = parts.slice(payloadIndex);
  if (hexParts.length === 0 || hexParts.length > 10000) return null;

  let decoded = '';
  for (const hex of hexParts) {
    if (!HEX_CHUNK_RE.test(hex)) return null;
    const codePoint = Number.parseInt(hex, 16);
    if (codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) return null;
    if (hex !== codePoint.toString(16).padStart(4, '0')) return null;
    decoded += String.fromCodePoint(codePoint);
  }
  return decoded;
}

/** Decode a handle only when its endpoint role matches the edge direction. */
export function decodeColumnHandle(
  handleId: string | null | undefined,
  role: 'src' | 'tgt',
): string | null {
  if (!handleId?.startsWith(`${role}-`)) return null;
  return decodeHandleId(handleId);
}
