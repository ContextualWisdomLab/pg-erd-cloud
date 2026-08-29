/** Encode a column name as the stable Unicode-code-point handle fragment. */
export function sanitizeHandleId(columnName: string): string {
  if (columnName.length === 0) return 'c-empty'

  let encoded = ''
  let separator = ''
  for (const character of columnName) {
    encoded += `${separator}${character.codePointAt(0)!.toString(16).padStart(4, '0')}`
    separator = '-'
  }

  return `c-${encoded}`
}

/** Build the stable source-side React Flow handle identifier for a column. */
export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

/** Build the stable target-side React Flow handle identifier for a column. */
export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}
