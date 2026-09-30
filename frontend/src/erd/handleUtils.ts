export function sanitizeHandleId(columnName: string): string {
  let encoded = '';
  let isFirst = true;
  // ⚡ Bolt: Use for...of instead of Array.from to prevent intermediate array allocations and reduce GC pressure.
  // for...of natively handles Unicode surrogate pairs (including emojis) perfectly.
  for (const char of columnName) {
    if (!isFirst) {
      encoded += '-';
    }
    isFirst = false;
    // for...of only yields non-empty Unicode scalars, so codePointAt(0) is defined.
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
