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

function parseStrictColumnName(handle: string, prefix: string): string | null {
  if (!handle || !handle.startsWith(prefix)) return null;
  const encoded = handle.slice(prefix.length);

  if (!encoded.startsWith('c-')) return null;
  const segments = encoded.slice(2);

  if (segments === 'empty') return '';

  const hexParts = segments.split('-');
  let decoded = '';

  for (const hex of hexParts) {
    if (!/^[0-9a-f]{4,}$/.test(hex)) return null; // strictly lowercase hex
    const codePoint = Number.parseInt(hex, 16);
    if (Number.isNaN(codePoint) || codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) return null;

    // Ensure canonical form (lowercase, padded, no extra zeroes unless needed for >0xffff)
    const canonicalHex = codePoint.toString(16).padStart(4, '0');
    if (hex !== canonicalHex) return null;

    try {
      decoded += String.fromCodePoint(codePoint);
    } catch {
      return null;
    }
  }
  return decoded;
}

export function parseSourceColumnNameFromHandle(handle: string | null | undefined): string | null {
  return handle ? parseStrictColumnName(handle, 'src-') : null;
}

export function parseTargetColumnNameFromHandle(handle: string | null | undefined): string | null {
  return handle ? parseStrictColumnName(handle, 'tgt-') : null;
}
