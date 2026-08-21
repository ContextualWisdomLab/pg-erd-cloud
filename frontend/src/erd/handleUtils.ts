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

export function parseColumnNameFromHandle(handleId: string | null | undefined): string | null {
  if (!handleId) return null;

  const parts = handleId.split('-');
  if (parts.length < 3 || !['src', 'tgt'].includes(parts[0]) || parts[1] !== 'c') {
    return null;
  }

  const encoded = parts.slice(2);
  if (encoded.length === 1 && encoded[0] === 'empty') {
    return '';
  }

  if (!encoded.every((segment) => /^[0-9a-fA-F]{4,6}$/.test(segment))) {
    return null;
  }

  try {
    return encoded.map((hex) => {
      const codePoint = Number.parseInt(hex, 16);
      if (codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) {
        throw new RangeError('invalid Unicode scalar');
      }
      return String.fromCodePoint(codePoint);
    }).join('');
  } catch {
    return null;
  }
}
