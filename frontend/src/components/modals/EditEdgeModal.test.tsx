import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { EditEdgeModal } from './EditEdgeModal';

afterEach(() => {
  cleanup();
});

describe('EditEdgeModal', () => {
  it('covers EditEdgeModal visibility and actions', () => {
    const setRelLabel = vi.fn()
    const onDelete = vi.fn()
    const onCancel = vi.fn()
    const onSubmit = vi.fn()
    const { rerender } = render(
      <EditEdgeModal
        editingEdge={null}
        relLabel=""
        setRelLabel={setRelLabel}
        onRelDelete={onDelete}
        onRelCancel={onCancel}
        onRelSubmit={onSubmit}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    rerender(
      <EditEdgeModal
        editingEdge={{ id: 'e', source: 'a', target: 'b', label: '' }}
        relLabel="fk_users"
        setRelLabel={setRelLabel}
        onRelDelete={onDelete}
        onRelCancel={onCancel}
        onRelSubmit={onSubmit}
      />,
    )
    expect(screen.getByText(/From: a/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('제약조건 이름 (Label)'), {
      target: { value: 'fk_changed' },
    })

    // test cancel delete
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false)
    fireEvent.click(screen.getByRole('button', { name: '삭제' }))
    expect(window.confirm).toHaveBeenCalledWith("이 관계를 삭제하시겠습니까?")
    expect(onDelete).not.toHaveBeenCalled()

    // test proceed delete
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true)
    fireEvent.click(screen.getByRole('button', { name: '삭제' }))
    expect(window.confirm).toHaveBeenCalledWith("이 관계를 삭제하시겠습니까?")
    expect(onDelete).toHaveBeenCalledOnce()

    fireEvent.click(screen.getByRole('button', { name: '취소' }))

    // Test submit preventing default
    const form = screen.getByRole('dialog')
    fireEvent.submit(form)

    expect(setRelLabel).toHaveBeenCalledWith('fk_changed')
    expect(onCancel).toHaveBeenCalledOnce()
    expect(onSubmit).toHaveBeenCalledOnce()
  })
});
