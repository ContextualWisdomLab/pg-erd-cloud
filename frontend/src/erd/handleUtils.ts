export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty';

  let encoded = '';
  // ⚡ Bolt: Use for...of loop instead of Array.from to avoid intermediate array allocations and GC overhead
  for (const char of columnName) {
    // Note: char may be empty string when columnName comes from Array.from, but with for...of loop, char will be non-empty scalar characters.
    const codePoint = char.codePointAt(0);
    if (codePoint !== undefined) {
      if (encoded.length > 0) encoded += '-';
      encoded += codePoint.toString(16).padStart(4, '0');
    }
  }

  return encoded ? `c-${encoded}` : 'c-empty';
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
