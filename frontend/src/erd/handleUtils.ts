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

export function decodeHandleId(handleId: string): string {
  if (!handleId || handleId.endsWith('-c-empty') || handleId === 'c-empty') {
    return '';
  }
  let encodedPart = handleId;
  let isSrc = false;
  let isTgt = false;
  if (handleId.startsWith('src-c-')) {
    encodedPart = handleId.slice(6);
    isSrc = true;
  } else if (handleId.startsWith('tgt-c-')) {
    encodedPart = handleId.slice(6);
    isTgt = true;
  } else if (handleId.startsWith('c-')) {
    encodedPart = handleId.slice(2);
  } else {
    throw new RangeError("Invalid handle format");
  }

  const parts = encodedPart.split('-');
  const decoded = parts.map(hex => {
    if (!/^[0-9a-fA-F]+$/.test(hex)) {
      throw new RangeError("Invalid handle format");
    }
    const codePoint = parseInt(hex, 16);
    if (isNaN(codePoint) || codePoint < 0 || codePoint > 0x10FFFF) {
       throw new RangeError("Invalid handle format");
    }
    return String.fromCodePoint(codePoint);
  }).join('');

  // Canonical identity verification
  let expected = sanitizeHandleId(decoded);
  if (isSrc) expected = "src-" + expected;
  else if (isTgt) expected = "tgt-" + expected;

  if (expected !== handleId) {
     throw new RangeError("Invalid handle format: not canonical");
  }

  return decoded;
}