import '@testing-library/jest-dom/vitest'

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AddTableModal } from './AddTableModal'

afterEach(cleanup)

function renderModal(name: string, onSubmit = vi.fn()) {
  const props = {
    isOpen: true,
    newTableName: name,
    setNewTableName: vi.fn(),
    onAddTableCancel: vi.fn(),
    onAddTableSubmit: onSubmit,
  }
  const result = render(<AddTableModal {...props} />)
  return { ...result, onSubmit, props }
}

describe('AddTableModal unavailable save state', () => {
  it('keeps the unavailable action focusable and described', () => {
    renderModal('   ')

    const input = screen.getByLabelText('테이블 이름')
    const save = screen.getByRole('button', { name: '저장' })
    const explanation = screen.getByText(
      '테이블 이름을 입력하면 저장할 수 있습니다.',
    )

    expect(save).toHaveAttribute('aria-disabled', 'true')
    expect(save).toHaveAttribute('aria-describedby', explanation.id)
    expect(input).toHaveAttribute('aria-describedby', explanation.id)
    expect(save).toHaveStyle({ opacity: 0.5, cursor: 'not-allowed' })

    save.focus()
    expect(save).toHaveFocus()
  })

  it('blocks click, Enter, Space, and direct form submission while unavailable', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderModal('')
    const save = screen.getByRole('button', { name: '저장' })

    fireEvent.click(save)
    save.focus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')
    fireEvent.submit(screen.getByRole('dialog'))

    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('removes the explanation and submits exactly once when a name is valid', () => {
    const onSubmit = vi.fn()
    const { rerender, props } = renderModal('', onSubmit)

    rerender(<AddTableModal {...props} newTableName=" users " />)

    const input = screen.getByLabelText('테이블 이름')
    const save = screen.getByRole('button', { name: '저장' })
    expect(save).toHaveAttribute('aria-disabled', 'false')
    expect(save).not.toHaveAttribute('aria-describedby')
    expect(input).not.toHaveAttribute('aria-describedby')
    expect(
      screen.queryByText('테이블 이름을 입력하면 저장할 수 있습니다.'),
    ).not.toBeInTheDocument()

    fireEvent.click(save)
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })
})
