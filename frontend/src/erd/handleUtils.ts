/**
 * Encode a persisted column name into the canonical React Flow handle payload.
 * The code-point format is a compatibility contract shared by graph rendering
 * and exporters, so equivalent refactors must preserve the exact bytes.
 */
export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty';

  let encoded = '';
  for (const char of columnName) {
    if (encoded.length > 0) {
      encoded += '-';
    }
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0');
  }

  return `c-${encoded}`;
}

/** Return the canonical source-endpoint handle for a persisted column name. */
export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

/** Return the canonical target-endpoint handle for a persisted column name. */
export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
