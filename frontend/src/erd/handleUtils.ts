export function sanitizeHandleId(columnName: string): string {
  const codes: string[] = [];
  // ⚡ Bolt: Avoid Array.from(string) to prevent intermediate array allocations and reduce GC overhead.
  for (const char of columnName) {
    codes.push(char.codePointAt(0)!.toString(16).padStart(4, '0'));
  }
  const encoded = codes.join('-');

  return `c-${encoded || 'empty'}`;
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
