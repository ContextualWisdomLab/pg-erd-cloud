export function createSanitizeHandleCache() {
  const cache = new Map<string, string>()

  return function sanitizeHandleId(columnName: string): string {
    const cached = cache.get(columnName)
    if (cached !== undefined) {
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
