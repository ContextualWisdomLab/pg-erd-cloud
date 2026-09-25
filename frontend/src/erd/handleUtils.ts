export function createSanitizeHandleCache(maxSize: number = 10000) {
  const cache = new Map<string, string>()

  return function sanitizeHandleId(columnName: string): string {
    if (cache.has(columnName)) {
      const cached = cache.get(columnName)!
      cache.delete(columnName)
      cache.set(columnName, cached)
      return cached
    }

    let encoded = ''
    for (const char of columnName) {
      const codePoint = char.codePointAt(0)
      if (codePoint !== undefined) {
        encoded += (encoded ? '-' : '') + codePoint.toString(16).padStart(4, '0')
      }
    }

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
