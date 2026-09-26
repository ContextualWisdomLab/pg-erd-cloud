export function sanitizeHandleId(columnName: string): string {
  let encoded = '';
  // ⚡ Bolt: Replace Array.from + join with a simple loop to reduce intermediate allocations and garbage collection overhead, especially for hot-path table rendering
  for (const char of columnName) {
    if (encoded.length > 0) encoded += '-';
    // String iterators yield full characters, natively handling surrogate pairs for emojis
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0');
  }

  return `c-${encoded || 'empty'}`;
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
