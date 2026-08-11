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

    try {
      const parts = encoded.split('-');
      for (const hex of parts) {
        if (!/^[0-9a-fA-F]+$/.test(hex)) return null;
      }
      return parts.map((hex) => String.fromCodePoint(parseInt(hex, 16))).join('');
    } catch (e) {
      return null;
    }
  }

  return null;
}
