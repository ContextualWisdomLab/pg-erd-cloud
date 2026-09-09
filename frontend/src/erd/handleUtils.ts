export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty';

  // ⚡ Bolt: Use for...of loop instead of Array.from to prevent intermediate array
  // allocations and reduce garbage collection pressure in this hot path.
  let encoded = '';
  let first = true;
  for (const char of columnName) {
    if (!first) {
      encoded += '-';
    }
    // for...of only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0');
    first = false;
  }

  return `c-${encoded}`;
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
