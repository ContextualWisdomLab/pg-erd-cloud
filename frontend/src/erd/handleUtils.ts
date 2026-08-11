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
  let decoded = '';
  for (const hex of hexParts) {
    if (!HEX_CHUNK_RE.test(hex)) {
      return null;
    }
    const codePoint = Number.parseInt(hex, 16);
    if (codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) {
      return null;
    }
    decoded += String.fromCodePoint(codePoint);
  }

  return decoded;
}

/** Decode only a canonical source-column handle. */
export function decodeSourceColumnHandleId(
  handleId: string | null | undefined,
): string | null {
  return handleId?.startsWith('src-c-') ? decodeHandleId(handleId) : null;
}

/** Decode only a canonical target-column handle. */
export function decodeTargetColumnHandleId(
  handleId: string | null | undefined,
): string | null {
  return handleId?.startsWith('tgt-c-') ? decodeHandleId(handleId) : null;
}
