import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AddTableModal } from './AddTableModal'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('AddTableModal accessible disabled state', () => {
  it('keeps an invalid save button focusable without submitting', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(
      <AddTableModal
        isOpen
        newTableName="   "
        setNewTableName={vi.fn()}
        onAddTableCancel={vi.fn()}
        onAddTableSubmit={onSubmit}
      />,
    )

    const saveButton = screen.getByRole('button', { name: '저장' })
    const dialog = screen.getByRole('dialog')

    expect(saveButton).toHaveAttribute('aria-disabled', 'true')
    expect(saveButton).toHaveStyle({ opacity: 0.5, cursor: 'not-allowed' })

    await user.click(saveButton)
    expect(onSubmit).not.toHaveBeenCalled()

    saveButton.focus()
    expect(saveButton).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(onSubmit).not.toHaveBeenCalled()

    saveButton.focus()
    await user.keyboard(' ')
    expect(onSubmit).not.toHaveBeenCalled()

    fireEvent.submit(dialog)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits a valid trimmed name exactly once per activation', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(
      <AddTableModal
        isOpen
        newTableName=" users "
        setNewTableName={vi.fn()}
        onAddTableCancel={vi.fn()}
        onAddTableSubmit={onSubmit}
      />,
    )

    const saveButton = screen.getByRole('button', { name: '저장' })
    const dialog = screen.getByRole('dialog')

    expect(saveButton).toHaveAttribute('aria-disabled', 'false')
    expect(saveButton).not.toHaveStyle({ opacity: 0.5, cursor: 'not-allowed' })

    await user.click(saveButton)
    expect(onSubmit).toHaveBeenCalledTimes(1)

    saveButton.focus()
    await user.keyboard('{Enter}')
    expect(onSubmit).toHaveBeenCalledTimes(2)

    saveButton.focus()
    await user.keyboard(' ')
    expect(onSubmit).toHaveBeenCalledTimes(3)

    fireEvent.submit(dialog)
    expect(onSubmit).toHaveBeenCalledTimes(4)
  })
})
