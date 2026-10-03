/** Create a bounded least-recently-used cache for stable column handle IDs. */
export function createHandleCache(maxSize: number = 1000) {
  if (!Number.isInteger(maxSize) || maxSize < 0) {
    throw new RangeError('maxSize must be a finite nonnegative integer');
  }

  const cache = new Map<string, string>();
  return (columnName: string): string => {
    let result = cache.get(columnName);
    if (result !== undefined) {
      // LRU behavior: move to end
      cache.delete(columnName);
      cache.set(columnName, result);
      return result;
    }

    let encoded = '';
    for (const char of columnName) {
      if (encoded) encoded += '-';
      // for...of only yields non-empty Unicode scalars, so codePointAt(0) is defined.
      encoded += char.codePointAt(0)!.toString(16).padStart(4, '0');
    }

    result = `c-${encoded || 'empty'}`;

    if (maxSize === 0) {
      return result;
    }

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

/** Encode a column name as a React Flow-safe handle identifier. */
export function sanitizeHandleId(columnName: string): string {
  return defaultCache(columnName);
}

/** Build the source-side handle identifier for a column. */
export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

/** Build the target-side handle identifier for a column. */
export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
