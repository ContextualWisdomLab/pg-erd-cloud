export function createSanitizeHandleCache(maxSize: number = 10000) {
  const cache = new Map<string, string>()

  return function sanitizeHandleId(columnName: string): string {
    if (cache.has(columnName)) {
      const cached = cache.get(columnName)!
      cache.delete(columnName)
      cache.set(columnName, cached)
      return cached
    }

    const encoded = Array.from(columnName, (char) => {
      // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
      return char.codePointAt(0)!.toString(16).padStart(4, '0')
    }).join('-')

    const result = `c-${encoded || 'empty'}`

    cache.set(columnName, result)

    if (cache.size > maxSize) {
      const firstKey = cache.keys().next().value
      if (firstKey !== undefined) {
        cache.delete(firstKey)
      }
    }

    return result
  }
}

export const sanitizeHandleId = createSanitizeHandleCache()

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
