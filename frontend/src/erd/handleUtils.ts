export function sanitizeHandleId(columnName: string): string {
  const encodedChars = [];
  for (const char of columnName) {
    // for...of iterates over Unicode code points natively
    encodedChars.push(char.codePointAt(0)!.toString(16).padStart(4, '0'));
  }
  const encoded = encodedChars.join('-');

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
