export function createHandleIdSanitizer(maxSize: number = 5000) {
  const cache = new Map<string, string>();
  return function sanitizeHandleId(columnName: string): string {
    if (cache.has(columnName)) {
      const cached = cache.get(columnName)!;
      cache.delete(columnName);
      cache.set(columnName, cached);
      return cached;
    }

    const encoded = Array.from(columnName, (char) => {
      return char.codePointAt(0)!.toString(16).padStart(4, '0');
    }).join('-');

    const result = `c-${encoded || 'empty'}`;

    if (cache.size >= maxSize) {
      const firstKey = cache.keys().next().value;
      if (firstKey !== undefined) {
        cache.delete(firstKey);
      }
    }

    cache.set(columnName, result);
    return result;
  };
}

// ⚡ Bolt: Cache expensive per-character string manipulations for high-frequency operations.
// Using a bounded LRU cache (utilizing Map's insertion-order preservation) to bypass
// redundant Array.from and codePointAt calls during React Flow renders and exports.
export const sanitizeHandleId = createHandleIdSanitizer();

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
