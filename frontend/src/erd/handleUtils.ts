const sanitizeCache = new Map<string, string>();
const parseCache = new Map<string, string>();

export function sanitizeHandleId(columnName: string): string {
  if (sanitizeCache.has(columnName)) {
    return sanitizeCache.get(columnName)!;
  }

  const encoded = Array.from(columnName, (char) => {
    // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  const result = `c-${encoded || 'empty'}`
  sanitizeCache.set(columnName, result);
  parseCache.set(result, columnName); // pre-populate reverse cache
  return result;
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}

export function parseColumnNameFromHandle(handleId: string | null | undefined): string {
  if (!handleId) return '';

  const cleanHandle = handleId.startsWith('src-')
    ? handleId.slice(4)
    : handleId.startsWith('tgt-')
      ? handleId.slice(4)
      : handleId;

  if (cleanHandle === 'c-empty') return '';

  if (parseCache.has(cleanHandle)) {
    return parseCache.get(cleanHandle)!;
  }

  if (!cleanHandle.startsWith('c-')) return cleanHandle;

  const parts = cleanHandle.slice(2).split('-');
  let result = '';
  for (const part of parts) {
    if (part) {
      result += String.fromCodePoint(parseInt(part, 16));
    }
  }

  parseCache.set(cleanHandle, result);
  sanitizeCache.set(result, cleanHandle); // populate forward cache
  return result;
}
