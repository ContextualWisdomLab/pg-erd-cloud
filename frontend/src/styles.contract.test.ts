import { afterEach, describe, expect, it } from 'vitest'

import './designTokens.css'
import './styles.css'

function element(className: string, parent: HTMLElement = document.body) {
  const node = document.createElement('div')
  node.className = className
  parent.append(node)
  return node
}

function declaration(selector: string, property: string, media: string | null = null) {
  let value = ''

  function visit(rules: CSSRuleList, activeMedia: string | null) {
    for (const rule of rules) {
      if (rule instanceof CSSStyleRule) {
        const selectors = rule.selectorText.split(',').map((item) => item.trim())
        const nextValue = rule.style.getPropertyValue(property).trim()
        if (activeMedia === media && selectors.includes(selector) && nextValue) {
          value = nextValue
        }
      } else if ('cssRules' in rule) {
        const conditionText = 'conditionText' in rule
          ? String(rule.conditionText)
          : activeMedia
        visit((rule as CSSGroupingRule).cssRules, conditionText)
      }
    }
  }

  for (const sheet of document.styleSheets) visit(sheet.cssRules, null)
  return value
}

function declarationAt(selector: string, property: string, viewportWidth: number) {
  let value = ''

  function visit(rules: CSSRuleList, applies: boolean) {
    for (const rule of rules) {
      if (rule instanceof CSSStyleRule) {
        const selectors = rule.selectorText.split(',').map((item) => item.trim())
        const nextValue = rule.style.getPropertyValue(property).trim()
        if (applies && selectors.includes(selector) && nextValue) value = nextValue
      } else if ('cssRules' in rule) {
        const maxWidth = 'conditionText' in rule
          ? String(rule.conditionText).match(/max-width:\s*(\d+)px/)?.[1]
          : undefined
        visit(
          (rule as CSSGroupingRule).cssRules,
          applies && (maxWidth === undefined || viewportWidth <= Number(maxWidth)),
        )
      }
    }
  }

  for (const sheet of document.styleSheets) visit(sheet.cssRules, true)
  return value
}

afterEach(() => {
  document.body.replaceChildren()
})

describe('live Figma layout contract', () => {
  it('preserves the 1440px editor split of 300px / 850px / 290px', () => {
    const layout = element('layout')
    const main = element('main', layout)
    const workspace = element('editorWorkspace', main)
    element('canvas', workspace)
    element('editorProperties', workspace)

    expect(
      getComputedStyle(document.documentElement)
        .getPropertyValue('--pg-size-layout-screen-sidebar-width')
        .trim(),
    ).toBe('300px')
    expect(declaration('.layout', 'grid-template-columns')).toBe(
      'var(--pg-size-layout-screen-sidebar-width) minmax(0, 1fr)',
    )
    expect(declaration('.editorWorkspace', 'grid-template-columns')).toBe(
      'minmax(0, 1fr) var(--pg-size-layout-properties-width)',
    )
    expect(
      getComputedStyle(document.documentElement)
        .getPropertyValue('--pg-size-layout-properties-width')
        .trim(),
    ).toBe('290px')
  })

  it('renders the dashboard metrics as four 240px cards with the live type scale', () => {
    const grid = element('metricGrid')
    const card = element('metricCard', grid)
    const label = document.createElement('span')
    const value = document.createElement('strong')
    card.append(label, value)

    expect(declaration('.metricGrid', 'grid-template-columns')).toBe(
      'repeat(4, 240px)',
    )
    expect(declaration('.metricGrid', 'gap')).toBe('var(--pg-spacing-16)')
    expect(declaration('.workspaceScreen', 'padding')).toBe(
      'var(--pg-spacing-24)',
    )
    expect(declaration('.metricCard', 'height')).toBe('96px')
    expect(declaration('.metricCard', 'border-radius')).toBe(
      'var(--pg-radius-sm)',
    )
    expect(declaration('.metricCard span', 'font-size')).toBe(
      'var(--pg-type-font-size-12)',
    )
    expect(declaration('.metricCard span', 'line-height')).toBe(
      'var(--pg-type-line-height-16)',
    )
    expect(declaration('.metricCard strong', 'font-size')).toBe(
      'var(--pg-type-font-size-18)',
    )
    expect(declaration('.metricCard strong', 'line-height')).toBe(
      'var(--pg-type-line-height-24)',
    )
  })

  it('uses app background for AuthGate and subtle modal borders', () => {
    element('authGate')
    element('modalShell modalShell--addTable')

    expect(declaration('.authGate', 'background')).toBe('var(--pg-color-bg-app)')
    expect(declaration('.modalShell--addTable', 'width')).toBe(
      'var(--pg-size-modal-add-table-width)',
    )
    expect(declaration('.modalShell', 'border')).toBe(
      '1px solid var(--pg-color-border-subtle)',
    )
    expect(declaration('.modalShell', 'max-width')).toBe(
      'calc(100vw - var(--pg-spacing-32))',
    )
  })

  it('uses the semantic brand text token for the brand lockup', () => {
    expect(declaration('.brandLockup', 'color')).toBe(
      'var(--pg-color-text-brand)',
    )
  })

  it('applies the Figma sans stack to native form controls', () => {
    for (const selector of ['button', 'input', 'select', 'textarea']) {
      expect(declaration(selector, 'font-family')).toBe(
        'var(--pg-type-font-family-css-stack)',
      )
    }
  })

  it('routes active navigation surfaces through theme-aware semantic tokens', () => {
    expect(declaration(':root', '--color-surface-active')).toBe(
      'var(--pg-color-surface-active)',
    )
    expect(declaration(':root', '--color-border-active')).toBe(
      'var(--pg-color-border-active)',
    )
    expect(declaration('.workspaceNav__item--active', 'color')).toBe(
      'var(--pg-color-text-brand)',
    )
  })

  it('pins React Flow handles, controls, and relationship lines to semantic tokens', () => {
    expect(declaration('.react-flow', '--xy-background-color')).toBe(
      'var(--pg-color-bg-canvas)',
    )
    expect(declaration('.react-flow', '--xy-minimap-background-color')).toBe(
      'var(--pg-color-surface-default)',
    )
    expect(declaration('.react-flow', '--xy-handle-background-color')).toBe(
      'transparent',
    )
    expect(declaration('.react-flow', '--xy-handle-border-color')).toBe(
      'var(--pg-color-border-control)',
    )
    expect(declaration('.react-flow', '--xy-controls-button-border-color')).toBe(
      'var(--pg-color-border-control)',
    )
    expect(declaration('.react-flow', '--xy-edge-stroke')).toBe(
      'var(--pg-color-border-control)',
    )
    expect(declaration('.react-flow', '--xy-connectionline-stroke')).toBe(
      'var(--pg-color-border-control)',
    )
    expect(declaration('.react-flow', '--xy-edge-stroke-selected')).toBe(
      'var(--pg-color-border-focus)',
    )
  })

  it('uses the high-contrast semantic border for form controls', () => {
    expect(declaration(':root', '--color-border')).toBe(
      'var(--pg-color-border-control)',
    )
    expect(declaration('.workspaceSearch input', 'border')).toBe(
      '1px solid var(--pg-color-border-control)',
    )
    expect(declaration('.editorProperties__search input', 'border')).toBe(
      '1px solid var(--pg-color-border-control)',
    )
    expect(declaration('.exportModal__linkInput', 'border')).toBe(
      '1px solid var(--pg-color-border-control)',
    )
  })

  it('keeps nested diagram status pills on their semantic state colors', () => {
    expect(declaration('.dataTable span', 'color')).toBe('')
    expect(declaration('.dataTable__row > span', 'color')).toBe(
      'var(--color-muted)',
    )
    expect(declaration('.statusPill--succeeded', 'color')).toBe(
      'var(--color-success-strong)',
    )
    expect(declaration('.statusPill--failed', 'color')).toBe(
      'var(--color-danger-strong)',
    )
  })

  it('keeps export hints distinct from section description copy', () => {
    expect(declaration('.exportModal__section p', 'font-size')).toBe('')
    expect(
      declaration(
        '.exportModal__section > p:not(.exportModal__hint)',
        'font-size',
      ),
    ).toBe('var(--pg-type-font-size-13)')
    expect(declaration('.exportModal__hint', 'color')).toBe(
      'var(--pg-color-text-muted)',
    )
    expect(declaration('.exportModal__hint', 'font-size')).toBe(
      'var(--pg-type-font-size-11)',
    )
  })

  it('styles EditTable text controls with semantic modal tokens', () => {
    const selectors = [
      '.editTableForm input:not([type])',
      '.editTableForm input[type="text"]',
      '.editTableForm textarea',
    ]

    for (const selector of selectors) {
      expect(declaration(selector, 'padding')).toBe(
        'var(--pg-spacing-8) var(--pg-spacing-10)',
      )
      expect(declaration(selector, 'border')).toBe(
        '1px solid var(--pg-color-border-control)',
      )
      expect(declaration(selector, 'border-radius')).toBe(
        'var(--pg-radius-sm)',
      )
      expect(declaration(selector, 'background')).toBe(
        'var(--pg-color-surface-default)',
      )
      expect(declaration(selector, 'color')).toBe(
        'var(--pg-color-text-primary)',
      )
    }
  })

  it('keeps desktop columns above 767px and stacks the shell and dialogs at 767px', () => {
    expect(declarationAt('.layout', 'grid-template-columns', 768)).toBe(
      'var(--pg-size-layout-screen-sidebar-width) minmax(0, 1fr)',
    )
    expect(declarationAt('.editorWorkspace', 'grid-template-columns', 768)).toBe(
      'minmax(0, 1fr) var(--pg-size-layout-properties-width)',
    )
    expect(declarationAt('.layout', 'grid-template-columns', 767)).toBe('1fr')
    expect(
      declarationAt('.editorWorkspace', 'grid-template-columns', 767),
    ).toBe('minmax(0, 1fr)')
    expect(declarationAt('.metricGrid', 'grid-template-columns', 767)).toBe(
      '1fr',
    )
    expect(
      declarationAt('.relationshipModal__actions', 'flex-direction', 767),
    ).toBe('column')
    expect(declarationAt('.editTableModal__actions', 'flex-direction', 767)).toBe(
      'column',
    )
  })
})
