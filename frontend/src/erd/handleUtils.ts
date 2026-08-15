/** Encode a column name as the stable Unicode-code-point handle identifier. */
export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty';

  let encoded = '';
  let first = true;
  for (const char of columnName) {
    if (!first) {
      encoded += '-';
    } else {
      first = false;
    }
    // for..of yields Unicode scalars, so codePointAt(0) is defined.
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0')
  }

  return `c-${encoded}`
}

/** Prefix a stable column handle for use as an edge source. */
export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

/** Prefix a stable column handle for use as an edge target. */
export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
