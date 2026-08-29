import type { CSSProperties } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'

import { designTokenValues } from './design-token-values'

type TokenKind = 'color' | 'radius' | 'space' | 'shadow'

type TokenDefinition = {
  label: string
  token: string
  kind: TokenKind
}

const exactTokenValue = (token: string): string => {
  const value = designTokenValues[token as keyof typeof designTokenValues]
  if (value === undefined) {
    throw new Error(`Storybook design-token inventory is missing ${token}`)
  }
  return value
}

const tokenGroups: Record<string, TokenDefinition[]> = {
  colors: [
    ['brand', '--color-brand'],
    ['text', '--color-text'],
    ['strong text', '--color-text-strong'],
    ['muted', '--color-muted'],
    ['strong muted', '--color-muted-strong'],
    ['soft muted', '--color-muted-soft'],
    ['disabled', '--color-disabled'],
    ['navigation text', '--color-nav-text'],
    ['success', '--color-success'],
    ['strong success', '--color-success-strong'],
    ['soft success', '--color-success-soft'],
    ['warning', '--color-warning'],
    ['danger', '--color-danger'],
    ['strong danger', '--color-danger-strong'],
    ['soft danger', '--color-danger-soft'],
    ['accent', '--color-accent'],
    ['surface', '--color-surface'],
    ['sidebar surface', '--color-surface-sidebar'],
    ['soft surface', '--color-surface-soft'],
    ['muted surface', '--color-surface-muted'],
    ['panel surface', '--color-surface-panel'],
    ['status surface', '--color-surface-status'],
    ['active surface', '--color-surface-active'],
    ['floating surface', '--color-surface-floating'],
    ['empty surface', '--color-surface-empty'],
    ['overlay', '--color-overlay'],
    ['border', '--color-border'],
    ['soft border', '--color-border-soft'],
    ['subtle border', '--color-border-subtle'],
    ['active border', '--color-border-active'],
  ].map(([label, token]) => ({ label, token, kind: 'color' })),
  layout: [
    ['control radius', '--radius-control'],
    ['panel radius', '--radius-panel'],
    ['control vertical space', '--space-control-y'],
    ['control horizontal space', '--space-control-x'],
  ].map(([label, token]) => ({
    label,
    token,
    kind: token.startsWith('--radius-') ? 'radius' : 'space',
  })),
  effects: [
    { label: 'highlight shadow', token: '--shadow-highlight', kind: 'shadow' },
    { label: 'modal shadow', token: '--shadow-modal', kind: 'shadow' },
  ],
}

const tokenPreviewStyle = ({ kind, token }: TokenDefinition): CSSProperties => {
  const base: CSSProperties = {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    display: 'inline-block',
    height: '24px',
    minWidth: '72px',
  }

  if (kind === 'color') return { ...base, background: `var(${token})` }
  if (kind === 'radius') return { ...base, borderRadius: `var(${token})` }
  if (kind === 'space') return { ...base, minWidth: 0, width: `var(${token})` }
  return { ...base, boxShadow: `var(${token})` }
}

const meta = {
  title: 'Design System/Design Tokens',
  parameters: { layout: 'padded' },
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const Inventory: Story = {
  render: () => (
    <div style={{ display: 'grid', gap: '24px', maxWidth: '960px' }}>
      {Object.entries(tokenGroups).map(([group, tokens]) => (
        <section key={group} aria-labelledby={`token-group-${group}`}>
          <h2 id={`token-group-${group}`} style={{ textTransform: 'capitalize' }}>{group}</h2>
          <div style={{ display: 'grid', gap: '8px' }}>
            {tokens.map(({ label, token, kind }) => (
              <div
                key={token}
                style={{
                  alignItems: 'center',
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '8px 12px',
                }}
              >
                <code style={{ flex: '1 1 220px', overflowWrap: 'anywhere' }}>{token}</code>
                <span style={{ color: 'var(--color-text)', flex: '1 1 140px' }}>{label}</span>
                <span style={{ color: 'var(--color-text)', flex: '1 1 220px' }}>
                  Exact value: <code>{exactTokenValue(token)}</code>
                </span>
                <span
                  aria-hidden="true"
                  data-token-preview="true"
                  style={tokenPreviewStyle({ label, token, kind })}
                />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  ),
}
