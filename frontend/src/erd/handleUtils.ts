// ⚡ Bolt: Cache handle IDs to avoid expensive Array.from and codePointAt operations
// during high-frequency React Flow renders and exports. Map preserves insertion order,
// allowing us to implement a lightweight LRU cache.
const handleCache = new Map<string, string>();
const MAX_CACHE_SIZE = 10000;

export function sanitizeHandleId(columnName: string): string {
  let cached = handleCache.get(columnName);
  if (cached) {
    // Move to end for LRU
    handleCache.delete(columnName);
    handleCache.set(columnName, cached);
    return cached;
  }

  const encoded = Array.from(columnName, (char) => {
    // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  cached = `c-${encoded || 'empty'}`;

  if (handleCache.size >= MAX_CACHE_SIZE) {
    // Delete oldest entry (first item in Map)
    const firstKey = handleCache.keys().next().value;
    if (firstKey !== undefined) {
      handleCache.delete(firstKey);
    }
  }

  handleCache.set(columnName, cached);
  return cached;
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
