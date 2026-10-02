export function sanitizeHandleId(columnName: string): string {
  let encoded = "";
  let isFirst = true;
  for (const char of columnName) {
    if (!isFirst) {
      encoded += "-";
    }
    // for...of only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0');
    isFirst = false;
  }

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
