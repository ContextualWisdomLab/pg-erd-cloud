export function sanitizeHandleId(columnName: string): string {
  let encoded = "";
  let first = true;
  for (const char of columnName) {
    if (!first) encoded += "-";
    // Using for...of string iteration correctly yields full Unicode code points
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0');
    first = false;
  }

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
