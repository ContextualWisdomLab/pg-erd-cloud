export function sanitizeHandleId(columnName: string): string {
  const encoded = Array.from(columnName, (char) => {
    // Array.from only yields non-empty Unicode scalars, so codePointAt(0) is defined.
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}

export function parseHandleId(handleStr: string): string {
  let hexStr = "";
  if (handleStr.startsWith("src-c-") || handleStr.startsWith("tgt-c-")) {
    hexStr = handleStr.slice(6);
  } else if (handleStr.startsWith("c-")) {
    hexStr = handleStr.slice(2);
  } else {
    return handleStr;
  }
  if (hexStr === "empty") return "";
  return hexStr.split("-").map((hex) => String.fromCodePoint(parseInt(hex, 16))).join("");
}
