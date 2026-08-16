import '@testing-library/jest-dom/vitest'
import type { Node } from '@xyflow/react'
import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { BUSINESS_GROUP_COLORS, type BusinessGroup } from '../../erd/businessGroups'
import type { TableNodeData } from '../../erd/convert'
import { GroupModal } from './GroupModal'

function RadiogroupHarness({ initialColor = BUSINESS_GROUP_COLORS[0] }: { initialColor?: string }) {
  const [color, setColor] = useState(initialColor)

  return (
    <GroupModal
      isOpen
      businessGroups={[] as BusinessGroup[]}
      newGroupName="Design"
      setNewGroupName={vi.fn()}
      newGroupColor={color}
      setNewGroupColor={setColor}
      nodes={[] as Node<TableNodeData>[]}
      onCloseGroupManager={vi.fn()}
      onCreateBusinessGroup={vi.fn()}
      onDeleteBusinessGroup={vi.fn()}
      onAssignBusinessGroup={vi.fn()}
    />
  )
}

describe('GroupModal color radiogroup', () => {
  it('exposes exactly one tab stop at the checked color', () => {
    render(<RadiogroupHarness initialColor={BUSINESS_GROUP_COLORS[1]} />)

    const radios = screen.getAllByRole('radio', { name: /^색상 / })
    expect(radios).toHaveLength(BUSINESS_GROUP_COLORS.length)
    expect(radios[1]).toHaveAttribute('aria-checked', 'true')
    expect(radios[1]).toHaveAttribute('tabindex', '0')

    radios.forEach((radio, index) => {
      if (index !== 1) {
        expect(radio).toHaveAttribute('aria-checked', 'false')
        expect(radio).toHaveAttribute('tabindex', '-1')
      }
    })
  })

  it.each([
    ['ArrowRight', 1],
    ['ArrowDown', 1],
    ['ArrowLeft', BUSINESS_GROUP_COLORS.length - 1],
    ['ArrowUp', BUSINESS_GROUP_COLORS.length - 1],
  ] as const)('moves focus and selection with %s', (key, expectedIndex) => {
    render(<RadiogroupHarness />)

    const radios = screen.getAllByRole('radio', { name: /^색상 / })
    radios[0]?.focus()
    fireEvent.keyDown(radios[0]!, { key })

    expect(radios[expectedIndex]).toHaveFocus()
    expect(radios[expectedIndex]).toHaveAttribute('aria-checked', 'true')
    expect(radios[expectedIndex]).toHaveAttribute('tabindex', '0')
    expect(radios[0]).toHaveAttribute('aria-checked', 'false')
    expect(radios[0]).toHaveAttribute('tabindex', '-1')
  })

  it('wraps from the last color to the first color', () => {
    const lastIndex = BUSINESS_GROUP_COLORS.length - 1
    render(<RadiogroupHarness initialColor={BUSINESS_GROUP_COLORS[lastIndex]} />)

    const radios = screen.getAllByRole('radio', { name: /^색상 / })
    radios[lastIndex]?.focus()
    fireEvent.keyDown(radios[lastIndex]!, { key: 'ArrowRight' })

    expect(radios[0]).toHaveFocus()
    expect(radios[0]).toHaveAttribute('aria-checked', 'true')
    expect(radios[0]).toHaveAttribute('tabindex', '0')
  })

  it('keeps an unsupported stored color unchanged until the user selects a palette value', () => {
    render(<RadiogroupHarness initialColor="not-in-palette" />)

    const radios = screen.getAllByRole('radio', { name: /^색상 / })
    expect(radios[0]).toHaveAttribute('tabindex', '0')
    radios.forEach((radio) => {
      expect(radio).toHaveAttribute('aria-checked', 'false')
    })

    radios[0]?.focus()
    fireEvent.keyDown(radios[0]!, { key: 'ArrowRight' })

    expect(radios[1]).toHaveFocus()
    expect(radios[1]).toHaveAttribute('aria-checked', 'true')
    expect(radios[1]).toHaveAttribute('tabindex', '0')
  })

  it('preserves native pointer activation and ignores unrelated keys', () => {
    render(<RadiogroupHarness />)

    const radios = screen.getAllByRole('radio', { name: /^색상 / })
    radios[0]?.focus()
    fireEvent.keyDown(radios[0]!, { key: 'Home' })

    expect(radios[0]).toHaveFocus()
    expect(radios[0]).toHaveAttribute('aria-checked', 'true')

    fireEvent.click(radios[2]!)
    expect(radios[2]).toHaveAttribute('aria-checked', 'true')
    expect(radios[2]).toHaveAttribute('tabindex', '0')
  })
})
