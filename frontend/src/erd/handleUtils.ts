// ⚡ Bolt: Cache string manipulation for high-frequency ERD operations
export function createHandleCache(maxSize: number = 1000) {
  const cache = new Map<string, string>();
  return (columnName: string): string => {
    let result = cache.get(columnName);
    if (result !== undefined) {
      // LRU behavior: move to end
      cache.delete(columnName);
      cache.set(columnName, result);
      return result;
    }

    const encoded = Array.from(columnName, (char) => {
      // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
      return char.codePointAt(0)!.toString(16).padStart(4, '0')
    }).join('-')

    result = `c-${encoded || 'empty'}`;

    if (cache.size >= maxSize) {
      // Evict oldest (first item in Map)
      const firstKey = cache.keys().next().value;
      if (firstKey !== undefined) {
        cache.delete(firstKey);
      }
    }

    cache.set(columnName, result);
    return result;
  };
}

const defaultCache = createHandleCache();

export function sanitizeHandleId(columnName: string): string {
  return defaultCache(columnName);
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
