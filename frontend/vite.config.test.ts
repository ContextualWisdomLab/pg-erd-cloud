import { describe, expect, it } from 'vitest'
import type { Plugin, UserConfig } from 'vite'

import config from './vite.config'

function devCspPlugin(): Plugin {
  const plugin = (config as UserConfig).plugins?.find(
    (candidate) =>
      typeof candidate === 'object' &&
      candidate !== null &&
      !Array.isArray(candidate) &&
      'name' in candidate &&
      candidate.name === 'dev-csp-inline-styles',
  )

  if (!plugin || typeof plugin !== 'object' || Array.isArray(plugin)) {
    throw new Error('dev-csp-inline-styles plugin is not configured')
  }

  return plugin as Plugin
}

function transformDevIndex(html: string): string {
  const hook = devCspPlugin().transformIndexHtml
  if (typeof hook !== 'function') {
    throw new Error('dev-csp-inline-styles transform is not callable')
  }

  const result = (hook as unknown as (source: string) => unknown)(html)
  if (typeof result !== 'string') {
    throw new Error('dev-csp-inline-styles transform must return HTML')
  }
  return result
}

describe('dev-csp-inline-styles', () => {
  it('is limited to the Vite serve command', () => {
    expect(devCspPlugin().apply).toBe('serve')
  })

  it('adds unsafe-inline only to the strict dev style-src directive', () => {
    const html = `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;">`

    expect(transformDevIndex(html)).toBe(
      `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;">`,
    )
  })

  it('fails closed when the expected strict style-src policy is absent', () => {
    const drifted = `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' https://styles.example;">`

    expect(() => transformDevIndex(drifted)).toThrow(/style-src/)
  })
})
