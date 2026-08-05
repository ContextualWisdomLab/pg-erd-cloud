export function sanitizeHandleId(columnName: string): string {
  if (!columnName) return 'c-empty'

  let encoded = ''
  let isFirst = true
  for (const char of columnName) {
    if (!isFirst) {
      encoded += '-'
    }
    encoded += char.codePointAt(0)!.toString(16).padStart(4, '0')
    isFirst = false
  }

  return `c-${encoded}`
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`
}

const HEX_CHUNK_RE = /^[0-9a-f]{4,6}$/

type HandleRole = 'column' | 'source' | 'target'

function canonicalHexChunk(codePoint: number): string {
  return codePoint.toString(16).padStart(4, '0')
}

function decodeHandleForRole(
  handleId: string | null | undefined,
  expectedRole?: HandleRole,
): string | null {
  if (!handleId) return null

  const parts = handleId.split('-')
  let payloadIndex = -1
  let role: HandleRole | null = null

  if (parts[0] === 'c') {
    payloadIndex = 1
    role = 'column'
  } else if (parts[0] === 'src' && parts[1] === 'c') {
    payloadIndex = 2
    role = 'source'
  } else if (parts[0] === 'tgt' && parts[1] === 'c') {
    payloadIndex = 2
    role = 'target'
  }

  if (payloadIndex === -1 || role === null) return null
  if (expectedRole !== undefined && role !== expectedRole) return null

  if (parts.length === payloadIndex + 1 && parts[payloadIndex] === 'empty') {
    return ''
  }

  const hexParts = parts.slice(payloadIndex)
  if (hexParts.length === 0) return null

  let decoded = ''
  for (const hex of hexParts) {
    if (!HEX_CHUNK_RE.test(hex)) {
      return null
    }
    const codePoint = Number.parseInt(hex, 16)
    if (codePoint > 0x10ffff || canonicalHexChunk(codePoint) !== hex) {
      return null
    }
    decoded += String.fromCodePoint(codePoint)
  }

  return decoded
}

export function decodeHandleId(handleId: string | null | undefined): string | null {
  return decodeHandleForRole(handleId)
}

export function decodeSourceColumnHandleId(
  handleId: string | null | undefined,
): string | null {
  return decodeHandleForRole(handleId, 'source')
}

export function decodeTargetColumnHandleId(
  handleId: string | null | undefined,
): string | null {
  return decodeHandleForRole(handleId, 'target')
}
