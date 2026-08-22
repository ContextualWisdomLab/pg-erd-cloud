import { readFileSync } from 'node:fs'

import { cleanup, render, screen, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { designTokenValues } from './design-token-values'
import { Inventory } from './design-tokens.stories'

const designTokensCss = readFileSync(new URL('./design-tokens.css', import.meta.url), 'utf8')
const expectedTokenValues = new Map(
  [...designTokensCss.matchAll(/(--[\w-]+)\s*:\s*([^;{}]+);/g)].map((match) => [
    match[1],
    match[2].trim(),
  ]),
)
const expectedTokens = Object.keys(designTokenValues)

const renderInventory = () => {
  const storyRender = Inventory.render as unknown as () => ReactElement
  render(storyRender())
}

const previewFor = (token: string): HTMLElement => {
  const row = screen.getByText(token).closest('div')
  expect(row).not.toBeNull()

  const preview = row?.querySelector('[data-token-preview="true"]')
  expect(preview).not.toBeNull()
  return preview as HTMLElement
}

afterEach(cleanup)

describe('Design token Storybook inventory', () => {
  it('keeps the executable value mirror identical to the runtime CSS source', () => {
    expect(Object.fromEntries(expectedTokenValues)).toEqual(designTokenValues)
  })

  it('renders every shared token under the semantic inventory groups', () => {
    renderInventory()

    expect(
      screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent),
    ).toEqual(['colors', 'layout', 'effects'])

    for (const token of expectedTokens) {
      expect(screen.getByText(token)).toBeTruthy()
    }
  })

  it('exposes each decorative visual preview through the CSS property owned by its token kind', () => {
    renderInventory()

    expect(previewFor('--color-brand').getAttribute('style')).toContain(
      'background: var(--color-brand)',
    )
    expect(previewFor('--radius-control').getAttribute('style')).toContain(
      'border-radius: var(--radius-control)',
    )

    const verticalSpacePreview = previewFor('--space-control-y')
    expect(verticalSpacePreview.getAttribute('style')).toContain('min-width: 0')
    expect(verticalSpacePreview.getAttribute('style')).toContain('width: var(--space-control-y)')

    expect(previewFor('--shadow-highlight').getAttribute('style')).toContain(
      'box-shadow: var(--shadow-highlight)',
    )
    expect(document.querySelectorAll('[data-token-preview="true"]')).toHaveLength(
      expectedTokens.length,
    )
  })

  it('shows every exact CSS value as text and keeps visual previews out of the accessibility tree', () => {
    renderInventory()

    for (const token of expectedTokens) {
      const row = screen.getByText(token).closest('div')
      expect(row).not.toBeNull()

      const exactValue = expectedTokenValues.get(token)
      expect(exactValue).toBeTruthy()
      expect(within(row as HTMLElement).getByText(exactValue as string)).toBeTruthy()
      expect(within(row as HTMLElement).queryByRole('img')).toBeNull()
      expect(previewFor(token).getAttribute('aria-hidden')).toBe('true')
    }
  })
})
