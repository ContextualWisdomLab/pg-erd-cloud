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

export function parseColumnNameFromHandle(handleId: string | null | undefined): string | undefined {
  if (!handleId) return undefined;

  let encoded: string;
  if (handleId.startsWith('src-c-') || handleId.startsWith('tgt-c-')) {
    encoded = handleId.slice(6);
  } else if (handleId.startsWith('c-')) {
    encoded = handleId.slice(2);
  } else {
    return undefined;
  }

  if (encoded === 'empty') return '';

  try {
    const parts = encoded.split('-');
    let result = '';
    for (const hex of parts) {
      if (!hex) return undefined;
      const cp = parseInt(hex, 16);
      if (Number.isNaN(cp)) return undefined;
      result += String.fromCodePoint(cp);
    }
    return result;
  } catch (e) {
    return undefined;
  }
}
