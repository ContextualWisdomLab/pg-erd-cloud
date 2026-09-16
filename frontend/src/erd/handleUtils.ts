// ⚡ Bolt: LRU Cache for handle ID generation
// Caching sanitizeHandleId results prevents expensive Array.from per-character string manipulations
// during high-frequency React Flow operations like dragging and resizing.
// This reduces GC pressure and speeds up graph renders for large diagrams.
const sanitizeCache = new Map<string, string>();
const MAX_CACHE_SIZE = 1000;

export function sanitizeHandleId(columnName: string): string {
  if (sanitizeCache.has(columnName)) {
    const cached = sanitizeCache.get(columnName)!;
    sanitizeCache.delete(columnName);
    sanitizeCache.set(columnName, cached);
    return cached;
  }

  const encoded = Array.from(columnName, (char) => {
    // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-');

  const result = `c-${encoded || 'empty'}`;

  sanitizeCache.set(columnName, result);
  if (sanitizeCache.size > MAX_CACHE_SIZE) {
    sanitizeCache.delete(sanitizeCache.keys().next().value!);
  }

  return result;
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
