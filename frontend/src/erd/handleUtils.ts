/** Encode a column name as the canonical opaque React Flow handle payload. */
export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty'

  let encoded = ''
  let isFirst = true
  for (const char of columnName) {
    if (!isFirst) {
      encoded += '-'
    }
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0')
    isFirst = false
  }

  return `c-${encoded}`
}

/** Build the canonical source-side handle identifier for a column name. */
export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

/** Build the canonical target-side handle identifier for a column name. */
export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}

const HEX_CHUNK_RE = /^[0-9a-f]{4,6}$/

/**
 * Decode a canonical column handle, returning null for malformed identifiers.
 *
 * Accepted forms are `c-*`, `src-c-*`, and `tgt-c-*`; each payload chunk must
 * be four to six lowercase hexadecimal digits or the single `empty` sentinel.
 */
export function decodeHandleId(handleId: string | null | undefined): string | null {
  if (!handleId) return null;

  const parts = handleId.split('-');
  let payloadIndex = -1;

  if (parts[0] === 'c') {
    payloadIndex = 1;
  } else if ((parts[0] === 'src' || parts[0] === 'tgt') && parts[1] === 'c') {
    payloadIndex = 2;
  }

  if (payloadIndex === -1) return null;

  if (parts.length === payloadIndex + 1 && parts[payloadIndex] === 'empty') {
    return '';
  }

  const hexParts = parts.slice(payloadIndex);
  if (hexParts.length === 0) return null;

  let decoded = '';
  for (const hex of hexParts) {
    if (!HEX_CHUNK_RE.test(hex)) {
      return null;
    }
    const codePoint = Number.parseInt(hex, 16);
    if (codePoint > 0x10ffff) {
      return null;
    }
    try {
      decoded += String.fromCodePoint(codePoint);
    } catch {
      /* v8 ignore next */
      return null;
    }
  }

  return decoded;
}
