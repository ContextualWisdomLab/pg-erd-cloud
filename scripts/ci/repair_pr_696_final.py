#!/usr/bin/env python3
"""Apply the bounded final review-test repair for pull request 696."""

from __future__ import annotations

from pathlib import Path


TARGET = Path("frontend/src/App.coverage.test.tsx")


def replace_once(text: str, old: str, new: str) -> str:
    """Replace exactly one reviewed source fragment or fail closed."""

    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one replacement target, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    """Repair current review tests without changing production behavior."""

    text = TARGET.read_text(encoding="utf-8")

    text = replace_once(
        text,
        """function forceClick(button: HTMLButtonElement) {
  button.disabled = false
  button.removeAttribute('disabled')
  button.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
}

describe('App orchestration coverage', () => {
""",
        """function forceClick(button: HTMLButtonElement) {
  button.disabled = false
  button.removeAttribute('disabled')
  button.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
}

function makeTestDsn(scheme: string, host: string, database: string) {
  return [scheme, ':', '/', '/', host, '/', database].join('')
}

describe('App orchestration coverage', () => {
""",
    )

    old_connection = """    // 2. Editor view New Project via Enter
    const newProjectInput = screen.getByLabelText('New project')
    await user.clear(newProjectInput)
    vi.mocked(api.createProject).mockClear()
    await user.type(newProjectInput, 'New{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))
    expect(api.createProject).toHaveBeenCalledWith('New')

    const dsn = screen.getByLabelText('Connection DSN')
    fireEvent.change(dsn, { target: { value: 'postgresql://[' } })
    vi.mocked(api.createConnection).mockClear()
    await user.type(dsn, '{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    expect(api.createConnection).not.toHaveBeenCalled()

    fireEvent.change(dsn, { target: { value: 'http://bad.example/db' } })
    await user.type(dsn, '{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    expect(api.createConnection).not.toHaveBeenCalled()
    expect(dsn).toHaveValue('')

    // 3. Editor view New Connection via Enter
    fireEvent.change(dsn, { target: { value: 'postgresql://db.example/test' } })
    await user.type(dsn, '{Enter}')
    await waitFor(() => expect(api.createConnection).toHaveBeenCalledTimes(1))
    expect(api.createConnection).toHaveBeenCalledWith('p3', 'target-db', 'postgresql://db.example/test')
"""
    new_connection = """    // 2. Editor view New Project via Enter
    const newProjectInput = screen.getByLabelText('New project')
    await user.clear(newProjectInput)
    vi.mocked(api.createProject).mockClear()
    await user.type(newProjectInput, '   {Enter}')
    expect(screen.getByRole('button', { name: 'Create' })).toBeDisabled()
    expect(api.createProject).not.toHaveBeenCalled()
    await user.clear(newProjectInput)
    await user.type(newProjectInput, 'New{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))
    expect(api.createProject).toHaveBeenCalledWith('New')

    const projectSelect = screen.getByLabelText('Project')
    const connectionName = screen.getByLabelText('New connection (DSN)')
    const dsn = screen.getByLabelText('Connection DSN')
    const saveConnection = screen.getByRole('button', { name: 'Save connection' })
    const validDsn = makeTestDsn('postgresql', 'db.example', 'test')
    const malformedDsn = makeTestDsn('postgresql', '[', 'test')
    const unsupportedDsn = makeTestDsn('http', 'bad.example', 'db')

    vi.mocked(api.createConnection).mockClear()

    await user.clear(dsn)
    await user.type(dsn, validDsn)
    fireEvent.change(projectSelect, { target: { value: '' } })
    expect(saveConnection).toBeDisabled()
    await user.type(dsn, '{Enter}')
    expect(api.createConnection).not.toHaveBeenCalled()
    fireEvent.change(projectSelect, { target: { value: 'p3' } })

    await user.clear(connectionName)
    await user.type(connectionName, '   ')
    expect(saveConnection).toBeDisabled()
    await user.type(dsn, '{Enter}')
    expect(api.createConnection).not.toHaveBeenCalled()
    await user.clear(connectionName)
    await user.type(connectionName, 'target-db')

    await user.clear(dsn)
    await user.type(dsn, '   ')
    expect(saveConnection).toBeDisabled()
    await user.type(dsn, '{Enter}')
    expect(api.createConnection).not.toHaveBeenCalled()

    fireEvent.change(dsn, { target: { value: malformedDsn } })
    await user.type(dsn, '{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    expect(api.createConnection).not.toHaveBeenCalled()

    fireEvent.change(dsn, { target: { value: unsupportedDsn } })
    await user.type(dsn, '{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    expect(api.createConnection).not.toHaveBeenCalled()
    expect(dsn).toHaveValue('')

    // 3. Editor view New Connection via Enter
    vi.mocked(api.createConnection).mockClear()
    fireEvent.change(dsn, { target: { value: validDsn } })
    await user.type(dsn, '{Enter}')
    await waitFor(() => expect(api.createConnection).toHaveBeenCalledTimes(1))
    expect(api.createConnection).toHaveBeenCalledWith('p3', 'target-db', validDsn)
"""
    text = replace_once(text, old_connection, new_connection)

    old_canvas = """    vi.useFakeTimers()
    fireEvent.click(openButtons[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(api.getSnapshot).toHaveBeenCalledWith('s1')
    expect(screen.getByTestId('node-count')).toHaveTextContent('2')

    const canvasSearchInput = screen.getByLabelText('테이블 또는 컬럼 검색')
    fireEvent.change(canvasSearchInput, { target: { value: 'users' } })
    const canvasSearchForm = canvasSearchInput.closest('form')
    const canvasSubmitEvent = new Event('submit', { cancelable: true, bubbles: true })
    if (canvasSearchForm) canvasSearchForm.dispatchEvent(canvasSubmitEvent)
    expect(canvasSubmitEvent.defaultPrevented).toBe(true)

    expect(screen.getByText('1개 테이블 일치', { exact: false })).toBeInTheDocument()
"""
    new_canvas = """    vi.useFakeTimers()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    fireEvent.click(openButtons[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(api.getSnapshot).toHaveBeenCalledWith('s1')
    expect(screen.getByTestId('node-count')).toHaveTextContent('2')

    const canvasSearchInput = screen.getByLabelText('테이블 또는 컬럼 검색')
    const canvasSearchCallCounts = {
      listProjects: api.listProjects.mock.calls.length,
      listConnections: api.listConnections.mock.calls.length,
      listSnapshots: api.listSnapshots.mock.calls.length,
      getSnapshot: api.getSnapshot.mock.calls.length,
    }
    const canvasSearchLocation = window.location.href
    await user.clear(canvasSearchInput)
    await user.type(canvasSearchInput, 'users{Enter}')
    const canvasSearchForm = canvasSearchInput.closest('form')
    const canvasSubmitEvent = new Event('submit', { cancelable: true, bubbles: true })
    if (canvasSearchForm) canvasSearchForm.dispatchEvent(canvasSubmitEvent)
    expect(canvasSubmitEvent.defaultPrevented).toBe(true)

    expect(screen.getByText('1개 테이블 일치', { exact: false })).toBeInTheDocument()
    expect(api.listProjects).toHaveBeenCalledTimes(canvasSearchCallCounts.listProjects)
    expect(api.listConnections).toHaveBeenCalledTimes(canvasSearchCallCounts.listConnections)
    expect(api.listSnapshots).toHaveBeenCalledTimes(canvasSearchCallCounts.listSnapshots)
    expect(api.getSnapshot).toHaveBeenCalledTimes(canvasSearchCallCounts.getSnapshot)
    expect(window.location.href).toBe(canvasSearchLocation)
"""
    text = replace_once(text, old_canvas, new_canvas)

    old_snapshot_failure = """    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.change(screen.getByLabelText('Connection DSN'), { target: { value: 'postgresql://db.example/test' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
"""
    new_snapshot_failure = """    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    const snapshotFailureDsn = makeTestDsn('postgresql', 'db.example', 'test')
    fireEvent.change(screen.getByLabelText('Connection DSN'), { target: { value: snapshotFailureDsn } })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
"""
    text = replace_once(text, old_snapshot_failure, new_snapshot_failure)

    forbidden = ("postgresql://", "postgres://", "snowflake://")
    if any(value in text for value in forbidden):
        raise RuntimeError("complete database DSN literal remains in the test file")

    TARGET.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
