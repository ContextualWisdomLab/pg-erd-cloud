export function createSanitizeHandleId(maxSize: number = 1000) {
  const cache = new Map<string, string>();

  return function sanitizeHandleId(columnName: string | null | undefined): string {
    if (!columnName) {
      return 'c-empty';
    }

    if (cache.has(columnName)) {
      const value = cache.get(columnName)!;
      cache.delete(columnName);
      cache.set(columnName, value);
      return value;
    }

    const encoded = Array.from(columnName, (char) => {
      // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
      return char.codePointAt(0)!.toString(16).padStart(4, '0');
    }).join('-');

    const value = `c-${encoded || 'empty'}`;
    cache.set(columnName, value);

    if (cache.size > maxSize) {
      const firstKey = cache.keys().next().value;
      if (firstKey !== undefined) {
        cache.delete(firstKey);
      }
    }

    return value;
  };
}

export const sanitizeHandleId = createSanitizeHandleId();

export function sourceColumnHandleId(columnName: string | null | undefined): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string | null | undefined): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
