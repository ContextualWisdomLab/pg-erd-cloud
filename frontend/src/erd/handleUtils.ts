const idCache = new Map<string, string>();
const MAX_CACHE_SIZE = 10000;

export function sanitizeHandleId(columnName: string): string {
  const cached = idCache.get(columnName);
  if (cached) {
    // move to end to keep LRU order
    idCache.delete(columnName);
    idCache.set(columnName, cached);
    return cached;
  }

  const encoded = Array.from(columnName, (char) => {
    // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  const res = `c-${encoded || 'empty'}`;
  idCache.set(columnName, res);
  if (idCache.size > MAX_CACHE_SIZE) {
    // Map iterates in insertion order, so this deletes the oldest
    const firstKey = idCache.keys().next().value;
    if (firstKey !== undefined) {
      idCache.delete(firstKey);
    }
  }
  return res;
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
