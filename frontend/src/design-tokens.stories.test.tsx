import { cleanup, render, screen, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { Inventory } from './design-tokens.stories'

const expectedTokens = [
  '--color-brand',
  '--color-text',
  '--color-text-strong',
  '--color-muted',
  '--color-muted-strong',
  '--color-muted-soft',
  '--color-disabled',
  '--color-nav-text',
  '--color-success',
  '--color-success-strong',
  '--color-success-soft',
  '--color-warning',
  '--color-danger',
  '--color-danger-strong',
  '--color-danger-soft',
  '--color-accent',
  '--color-surface',
  '--color-surface-sidebar',
  '--color-surface-soft',
  '--color-surface-muted',
  '--color-surface-panel',
  '--color-surface-status',
  '--color-surface-active',
  '--color-surface-floating',
  '--color-surface-empty',
  '--color-overlay',
  '--color-border',
  '--color-border-soft',
  '--color-border-subtle',
  '--color-border-active',
  '--radius-control',
  '--radius-panel',
  '--space-control-y',
  '--space-control-x',
  '--shadow-highlight',
  '--shadow-modal',
]

const renderInventory = () => {
  const storyRender = Inventory.render as unknown as () => ReactElement
  render(storyRender())
}

afterEach(cleanup)

describe('Design token Storybook inventory', () => {
  it('renders every shared token under the semantic inventory groups', () => {
    renderInventory()

    expect(
      screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent),
    ).toEqual(['colors', 'layout', 'effects'])

    for (const token of expectedTokens) {
      expect(screen.getByText(token)).toBeTruthy()
    }
  })

  it('exposes each visual preview as a named image using its CSS custom property', () => {
    renderInventory()

    const brandPreview = screen.getByRole('img', { name: 'brand token preview' })
    expect(brandPreview.getAttribute('style')).toContain('var(--color-brand)')

    const layoutSection = screen.getByRole('heading', { name: 'layout' }).closest('section')
    expect(layoutSection).not.toBeNull()
    expect(
      within(layoutSection as HTMLElement).getByRole('img', {
        name: 'control radius token preview',
      }).getAttribute('style'),
    ).toContain('var(--radius-control)')

    const verticalSpacePreview = within(layoutSection as HTMLElement).getByRole('img', {
      name: 'control vertical space token preview',
    })
    expect(verticalSpacePreview.getAttribute('style')).toContain('min-width: 0')
    expect(verticalSpacePreview.getAttribute('style')).toContain('var(--space-control-y)')

    expect(screen.getAllByRole('img')).toHaveLength(expectedTokens.length)
  })
})
