export function sanitizeHandleId(columnName: string): string {
  // ⚡ Bolt: Replace Array.from() with for...of to avoid intermediate array allocation
  // during frequent handle ID generation in high-frequency rendering paths.
  let encoded = '';
  for (const char of columnName) {
    if (encoded) encoded += '-';
    // for...of natively handles Unicode surrogate pairs (including emojis).
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
