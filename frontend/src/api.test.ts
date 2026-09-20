import { describe, expect, it } from 'vitest'

import { publicShareIdFromPath, shareLinkUrlFromPath } from './api'

describe('shareLinkUrlFromPath', () => {
  it('builds an absolute share URL from the backend path', () => {
    const url = new URL(shareLinkUrlFromPath('/api/share/share-123'))

    expect(url.pathname).toBe('/share/share-123')
  })

  it('round-trips encoded public share identifiers', () => {
    const url = new URL(shareLinkUrlFromPath('/api/share/팀 공유'))

    expect(url.pathname).toBe('/share/%ED%8C%80%20%EA%B3%B5%EC%9C%A0')
    expect(publicShareIdFromPath(url.pathname)).toBe('팀 공유')
  })

  it('rejects missing or unrelated paths', () => {
    expect(() => shareLinkUrlFromPath(undefined)).toThrow('invalid share URL path')
    expect(() => shareLinkUrlFromPath('/api/projects/p/share-links')).toThrow(
      'invalid share URL path',
    )
  })

  it('recognizes only the public share view path', () => {
    expect(publicShareIdFromPath('/share/share-123')).toBe('share-123')
    expect(publicShareIdFromPath('/share/share-123/')).toBe('share-123')
    expect(publicShareIdFromPath('/share/%')).toBeNull()
    expect(publicShareIdFromPath('/share/%E0%A4%A')).toBeNull()
    expect(publicShareIdFromPath('/share/')).toBeNull()
    expect(publicShareIdFromPath('/api/share/share-123')).toBeNull()
    expect(publicShareIdFromPath('/share/a/b')).toBeNull()
  })
})
