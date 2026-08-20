import type { Meta, StoryObj } from '@storybook/react-vite'

const tokenGroups = {
  semantic: [
    ['brand', '--color-brand'],
    ['text', '--color-text'],
    ['muted', '--color-muted'],
    ['success', '--color-success'],
    ['warning', '--color-warning'],
    ['danger', '--color-danger'],
    ['surface', '--color-surface'],
    ['border', '--color-border'],
  ],
  layout: [
    ['control radius', '--radius-control'],
    ['panel radius', '--radius-panel'],
    ['control vertical space', '--space-control-y'],
    ['control horizontal space', '--space-control-x'],
  ],
} as const

const meta = {
  title: 'Design System/Design Tokens',
  parameters: { layout: 'padded' },
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const Inventory: Story = {
  render: () => (
    <div style={{ display: 'grid', gap: '24px', maxWidth: '720px' }}>
      {Object.entries(tokenGroups).map(([group, tokens]) => (
        <section key={group} aria-labelledby={`token-group-${group}`}>
          <h2 id={`token-group-${group}`} style={{ textTransform: 'capitalize' }}>{group}</h2>
          <div style={{ display: 'grid', gap: '8px' }}>
            {tokens.map(([label, token]) => (
              <div key={token} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <code style={{ minWidth: '220px' }}>{token}</code>
                <span style={{ color: 'var(--color-text)' }}>{label}</span>
                <span
                  aria-label={`${label} token value`}
                  style={{
                    background: `var(${token})`,
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-control)',
                    display: 'inline-block',
                    height: '24px',
                    minWidth: '72px',
                  }}
                />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  ),
}
