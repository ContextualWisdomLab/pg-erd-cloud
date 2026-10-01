export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return "c-empty";

  let encoded = "";
  let i = 0;
  for (const char of columnName) {
    if (i > 0) encoded += "-";
    // for...of iterates over Unicode code points natively
    encoded += char.codePointAt(0)!.toString(16).padStart(4, "0");
    i++;
  }

  return `c-${encoded}`;
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
