import { readFileSync } from 'node:fs'
import { resolve, sep } from 'node:path'

import { describe, expect, it } from 'vitest'

import { headersFor, securityHeaders } from './static-headers.mjs'

describe('production static response headers', () => {
  it('copies every runtime module imported by the static server into the image', () => {
    const dockerfile = readFileSync(resolve(process.cwd(), 'Dockerfile.prod'), 'utf8')
    expect(dockerfile).toContain(
      'COPY --chown=node:node serve-static.mjs static-headers.mjs /app/'
    )
  })

  it.each(['/share', '/share/public-link'])(
    'prevents storage of bearer share routes at %s',
    (pathname) => {
      expect(headersFor(`${sep}app${sep}dist${sep}index.html`, pathname)).toMatchObject({
        ...securityHeaders,
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store'
      })
    }
  )

  it('keeps fingerprinted assets immutable', () => {
    expect(
      headersFor(`${sep}app${sep}dist${sep}assets${sep}app.js`, '/assets/app.js')[
        'Cache-Control'
      ]
    ).toBe('public, max-age=31536000, immutable')
  })

  it('revalidates ordinary non-fingerprinted files', () => {
    expect(headersFor(`${sep}app${sep}dist${sep}index.html`, '/')['Cache-Control']).toBe(
      'no-cache'
    )
  })

  it('falls back to a binary MIME type for unknown extensions', () => {
    expect(headersFor(`${sep}app${sep}dist${sep}artifact.bin`, '/artifact.bin')).toMatchObject({
      'Content-Type': 'application/octet-stream',
      'Cache-Control': 'no-cache'
    })
  })
})
