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

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}

const HEX_CHUNK_RE = /^[0-9a-f]{4,6}$/

function hasCanonicalRole(
  handleId: string | null | undefined,
  role: 'src' | 'tgt',
): handleId is string {
  return Boolean(handleId?.startsWith(`${role}-c-`));
}


/**
 * Reverses the encoding applied by sanitizeHandleId to retrieve the native column string.
 * This lookup strictly validates the structure and bounds lengths (max 10k items)
 * to prevent ReDoS/OOM attacks from excessively sized hex strings.
 */
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

  if (parts.length === payloadIndex + 1 && parts[payloadIndex] === 'empty') {
    return '';
  }

  const hexParts = parts.slice(payloadIndex);
  if (hexParts.length > 10000) return null;
  if (hexParts.length === 0) return null;

  let decoded = '';
  for (const hex of hexParts) {
    if (!HEX_CHUNK_RE.test(hex)) {
      return null;
    }
    const codePoint = Number.parseInt(hex, 16);
    if (codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) {
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

/** Decodes a canonical source-column handle and rejects every other role. */
export function decodeSourceColumnHandleId(handleId: string | null | undefined): string | null {
  return hasCanonicalRole(handleId, 'src') ? decodeHandleId(handleId) : null;
}

/** Decodes a canonical target-column handle and rejects every other role. */
export function decodeTargetColumnHandleId(handleId: string | null | undefined): string | null {
  return hasCanonicalRole(handleId, 'tgt') ? decodeHandleId(handleId) : null;
}
