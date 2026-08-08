const HANDLE_HEX_TOKEN_RE = /^[0-9a-f]{4,6}$/i;

/** Encode a column name into the stable handle fragment used by ERD edges. */
export function sanitizeHandleId(columnName: string): string {
  const encoded = Array.from(columnName, (char) => {
    // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
}

/** Build the source-side edge handle for a column name. */
export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

/** Build the target-side edge handle for a column name. */
export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}

/**
 * Decode a source or target column handle back to its original column name.
 *
 * Returns `null` for malformed, oversized, or invalid Unicode encodings instead
 * of accepting a partially parsed hexadecimal token.
 */
export function parseColumnNameFromHandle(handleId: string | undefined | null): string | null {
  if (!handleId) return null;
  if (handleId.length > 512) return null;

  let prefixRemoved = handleId;
  if (handleId.startsWith('src-')) {
    prefixRemoved = handleId.slice(4);
  } else if (handleId.startsWith('tgt-')) {
    prefixRemoved = handleId.slice(4);
  }

  if (prefixRemoved.startsWith('c-')) {
    const encoded = prefixRemoved.slice(2);
    if (encoded === 'empty') {
      return '';
    }

    const codePoints = encoded.split('-');
    if (!codePoints.every((hex) => HANDLE_HEX_TOKEN_RE.test(hex))) {
      return null;
    }

    try {
      return codePoints
        .map((hex) => String.fromCodePoint(parseInt(hex, 16)))
        .join('');
    } catch {
      return null;
    }
  }

  return null;
}
