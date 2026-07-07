import { describe, expect, it } from 'vitest'

import { shareLinkUrlFromPath } from './api'

describe('shareLinkUrlFromPath', () => {
  it('builds an absolute share URL from the backend path', () => {
    const url = new URL(shareLinkUrlFromPath('/api/share/share-123'))

    expect(url.pathname).toBe('/api/share/share-123')
  })

  it('rejects missing or unrelated paths', () => {
    expect(() => shareLinkUrlFromPath(undefined)).toThrow('invalid share URL path')
    expect(() => shareLinkUrlFromPath('/api/projects/p/share-links')).toThrow(
      'invalid share URL path',
    )
  })
})
