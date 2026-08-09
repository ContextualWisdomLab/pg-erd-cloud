import { describe, expect, it } from 'vitest'

import './designTokens.css'

function token(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function resolvedToken(name: string) {
  let value = token(name)
  const visited = new Set<string>()
  while (value.startsWith('var(')) {
    const referencedName = value.match(/^var\((--[^,)]+)/)?.[1]
    if (!referencedName || visited.has(referencedName)) break
    visited.add(referencedName)
    value = token(referencedName)
  }
  return value
}

function relativeLuminance(hex: string) {
  const channels = hex
    .slice(1)
    .match(/.{2}/g)!
    .map((value) => Number.parseInt(value, 16) / 255)
    .map((value) =>
      value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4,
    )
  return 0.2126 * channels[0]! + 0.7152 * channels[1]! + 0.0722 * channels[2]!
}

function contrastRatio(foreground: string, background: string) {
  const lighter = Math.max(relativeLuminance(foreground), relativeLuminance(background))
  const darker = Math.min(relativeLuminance(foreground), relativeLuminance(background))
  return (lighter + 0.05) / (darker + 0.05)
}

describe('live Figma design token contract', () => {
  it.each([
    ['layout/sidebar-width', '--pg-size-layout-sidebar-width', '360px'],
    ['layout/mobile-breakpoint', '--pg-size-layout-mobile-breakpoint', '767px'],
    ['layout/auth-max-width', '--pg-size-layout-auth-max-width', '460px'],
    ['erd/table-node-width', '--pg-size-erd-table-node-width', '280px'],
    ['erd/grid-columns', '--pg-size-erd-grid-columns', '4'],
    ['erd/grid-x-gap', '--pg-size-erd-grid-x-gap', '320px'],
    ['erd/grid-y-gap', '--pg-size-erd-grid-y-gap', '220px'],
    ['modal/add-table-width', '--pg-size-modal-add-table-width', '300px'],
    ['modal/relationship-width', '--pg-size-modal-relationship-width', '320px'],
    ['modal/export-width', '--pg-size-modal-export-width', '500px'],
    ['modal/group-width', '--pg-size-modal-group-width', '680px'],
    ['modal/cardinality-width', '--pg-size-modal-cardinality-width', '760px'],
    ['modal/edit-table-width', '--pg-size-modal-edit-table-width', '800px'],
    ['control/number-input-width', '--pg-size-control-number-input-width', '140px'],
    ['control/swatch-size', '--pg-size-control-swatch-size', '28px'],
    ['empty/icon-size', '--pg-size-empty-icon-size', '40px'],
    ['handle/column-size', '--pg-size-handle-column-size', '6px'],
    ['opacity/disabled', '--pg-opacity-disabled', '0.6'],
    ['font/family/figma-sans', '--pg-type-font-family-figma-sans', 'Inter'],
  ])('maps %s to %s: %s', (_figmaName, cssName, value) => {
    expect(
      getComputedStyle(document.documentElement).getPropertyValue(cssName).trim(),
    ).toBe(value)
  })

  it('keeps primary action text readable in dark mode', () => {
    document.documentElement.dataset.theme = 'dark'
    expect(
      getComputedStyle(document.documentElement)
        .getPropertyValue('--pg-color-text-inverse')
        .trim(),
    ).toBe('#ffffff')
    delete document.documentElement.dataset.theme
  })

  it('uses the bundled Figma sans family first in the application stack', () => {
    expect(token('--pg-type-font-family-css-stack')).toBe(
      'var(--pg-type-font-family-figma-sans),system-ui,-apple-system,"Segoe UI",Roboto,sans-serif',
    )
  })

  it('provides dark semantic active navigation surfaces', () => {
    document.documentElement.dataset.theme = 'dark'
    expect(token('--pg-color-surface-active')).toBe('#162c5a')
    expect(token('--pg-color-border-active')).toBe('#6e95eb')
    delete document.documentElement.dataset.theme
  })

  it.each(['light', 'dark'] as const)(
    'keeps success status text readable in %s mode',
    (theme) => {
      if (theme === 'dark') document.documentElement.dataset.theme = 'dark'
      else delete document.documentElement.dataset.theme

      expect(
        contrastRatio(
          resolvedToken('--pg-color-text-success'),
          resolvedToken('--pg-color-group-green-surface'),
        ),
      ).toBeGreaterThanOrEqual(4.5)

      delete document.documentElement.dataset.theme
    },
  )

  it.each(['light', 'dark'] as const)(
    'keeps brand lockup text readable in %s mode',
    (theme) => {
      if (theme === 'dark') document.documentElement.dataset.theme = 'dark'
      else delete document.documentElement.dataset.theme

      expect(
        contrastRatio(
          resolvedToken('--pg-color-text-brand'),
          resolvedToken('--pg-color-bg-app'),
        ),
      ).toBeGreaterThanOrEqual(4.5)

      delete document.documentElement.dataset.theme
    },
  )

  it.each(['light', 'dark'] as const)(
    'keeps active navigation text readable in %s mode',
    (theme) => {
      if (theme === 'dark') document.documentElement.dataset.theme = 'dark'
      else delete document.documentElement.dataset.theme

      expect(
        contrastRatio(
          resolvedToken('--pg-color-text-brand'),
          resolvedToken('--pg-color-surface-active'),
        ),
      ).toBeGreaterThanOrEqual(4.5)

      delete document.documentElement.dataset.theme
    },
  )
})
