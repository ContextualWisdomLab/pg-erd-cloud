export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty';

  let encoded = '';
  let isFirst = true;
  // ⚡ Bolt: Using for...of avoids intermediate array allocation and GC overhead
  // that would be caused by Array.from(string) in this hot path.
  for (const char of columnName) {
    if (!isFirst) encoded += '-';
    // for...of only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0');
    isFirst = false;
  }

  return `c-${encoded}`;
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
